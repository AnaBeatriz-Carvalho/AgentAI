"""Coleta e persiste o corpus de discursos do Senado em SQLite (Fase 1).

Percorre um intervalo de datas em janelas menores que o limite da API, extrai os
pronunciamentos do endpoint ``plenario/lista/discursos`` e grava tudo no banco local
(``src.data.db``) com upsert idempotente. Diferente do pipeline do app, aqui **nada é
classificado nem cacheado em memória**: o objetivo é materializar um corpus estável e
reprodutível para o gabarito e as métricas de avaliação.

Campos capturados (superset do que o app usa hoje), úteis para a avaliação:
- ``resumo`` e ``indexacao``: base para o classificador por palavra-chave e apoio à
  anotação humana (a ``Indexacao`` é a indexação oficial do Senado).
- ``texto_integral_url``: permite recuperar o texto completo (dimensão factual/RAG).
- ``tipo_autor``: distingue Senador(a) de autores externos (filtrável no gabarito).
- ``codigo_sessao``/``data_sessao``: rastreabilidade da fonte (dimensão 4.4).

Exemplos::

    python3 scripts/coletar_corpus.py --inicio 2024-01-01 --fim 2026-08-01
    python3 scripts/coletar_corpus.py --inicio 2026-05-01 --fim 2026-06-01 --janela-dias 15
"""

from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# Permite rodar como script solto (python3 scripts/coletar_corpus.py) resolvendo a raiz.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config.constants import SENADO_API_DISCURSOS, SENADO_HEADERS, REQUEST_TIMEOUT
from src.data import db


def _txt(node: ET.Element, tag: str) -> str:
    """Texto de um filho direto, ou string vazia."""
    el = node.find(tag)
    return el.text.strip() if el is not None and el.text is not None else ""


def _parse_discursos(xml_text: str) -> list[dict]:
    """Extrai os pronunciamentos do XML, carregando também metadados da sessão-pai."""
    root = ET.fromstring(xml_text)
    registros: list[dict] = []
    for sessao in root.findall(".//Sessao"):
        cod_sessao = _txt(sessao, "CodigoSessao")
        tipo_sessao = _txt(sessao, "DescricaoSessao") or _txt(sessao, "TipoSessao")
        data_sessao = _txt(sessao, "DataSessao")
        for p in sessao.findall(".//Pronunciamento"):
            codigo = _txt(p, "CodigoPronunciamento") or _txt(p, "Codigo")
            if not codigo:
                continue
            registros.append({
                "codigo_pronunciamento": codigo,
                "data": _txt(p, "Data"),
                "casa": _txt(p, "Casa"),
                "tipo_autor": _txt(p, "TipoAutor"),
                "funcao_autor": _txt(p, "FuncaoAutor"),
                "nome_autor": _txt(p, "NomeAutor"),
                "partido": _txt(p, "Partido") or _txt(p, "SiglaPartido"),
                "uf": _txt(p, "UF") or _txt(p, "SiglaUf"),
                "cargo_autor": _txt(p, "CargoAutor"),
                "orgao_autor": _txt(p, "OrgaoAutor"),
                "resumo": _txt(p, "Resumo"),
                "indexacao": _txt(p, "Indexacao"),
                "texto_integral_url": _txt(p, "TextoIntegralTxt") or _txt(p, "TextoIntegral"),
                "codigo_sessao": cod_sessao,
                "tipo_sessao": tipo_sessao,
                "data_sessao": data_sessao,
            })
    return registros


def _janelas(inicio: date, fim: date, dias: int):
    """Gera intervalos [ini, fim] de no máximo `dias` cobrindo [inicio, fim]."""
    atual = inicio
    while atual <= fim:
        prox = min(atual + timedelta(days=dias - 1), fim)
        yield atual, prox
        atual = prox + timedelta(days=1)


def coletar(inicio: date, fim: date, caminho_db: str, janela_dias: int, sleep: float) -> None:
    con = db.conectar(caminho_db)
    db.criar_schema(con)

    total_janelas = sum(1 for _ in _janelas(inicio, fim, janela_dias))
    print(f"Coletando discursos de {inicio} a {fim} em {total_janelas} janela(s) "
          f"de até {janela_dias} dias → {caminho_db}\n")

    total_novos = 0
    for i, (ini, f) in enumerate(_janelas(inicio, fim, janela_dias), start=1):
        url = f"{SENADO_API_DISCURSOS}/{ini:%Y%m%d}/{f:%Y%m%d}"
        try:
            resp = requests.get(url, headers=SENADO_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            registros = _parse_discursos(resp.text)
        except requests.HTTPError as e:
            # 404 costuma ser janela sem sessão (recesso/fim de semana): não é erro fatal.
            if e.response is not None and e.response.status_code == 404:
                print(f"  [{i}/{total_janelas}] {ini}..{f}: sem discursos (404)")
                continue
            print(f"  [{i}/{total_janelas}] {ini}..{f}: ERRO HTTP {e}")
            continue
        except (requests.RequestException, ET.ParseError) as e:
            print(f"  [{i}/{total_janelas}] {ini}..{f}: falha ({e})")
            continue

        n = db.upsert_discursos(con, registros)
        total_novos += n
        print(f"  [{i}/{total_janelas}] {ini}..{f}: {n} pronunciamentos")
        time.sleep(sleep)

    total_banco = db.contar(con, "discursos")
    senadores = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%'"
    ).fetchone()[0]
    con.close()

    print(f"\n✅ Coleta concluída. {total_novos} pronunciamentos processados nesta execução.")
    print(f"   Total no banco (após dedup por código): {total_banco}")
    print(f"   Destes, autores Senador(a): {senadores} "
          f"({senadores / total_banco * 100:.1f}%)" if total_banco else "")


def _data(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    ap = argparse.ArgumentParser(description="Coleta discursos do Senado para SQLite.")
    ap.add_argument("--inicio", type=_data, required=True, help="Data inicial (YYYY-MM-DD).")
    ap.add_argument("--fim", type=_data, required=True, help="Data final (YYYY-MM-DD).")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO), help="Caminho do SQLite.")
    ap.add_argument("--janela-dias", type=int, default=15, help="Tamanho da janela (dias).")
    ap.add_argument("--sleep", type=float, default=1.0, help="Pausa entre requisições (s).")
    args = ap.parse_args()

    if args.inicio > args.fim:
        ap.error("--inicio deve ser <= --fim")
    coletar(args.inicio, args.fim, args.db, args.janela_dias, args.sleep)


if __name__ == "__main__":
    main()
