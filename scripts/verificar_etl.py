"""Verificação empírica do ETL (dimensão 4.1) sobre o corpus SQLite.

Produz números reais para as três subdimensões do handoff:

- **Completude:** taxa de preenchimento dos campos essenciais (geral e no subconjunto de
  senadores) e proporção de registros com TODOS os essenciais preenchidos.
- **Consistência:** duplicatas (código e conteúdo), datas inválidas/futuras, UFs inválidas,
  vínculos incorretos (senador sem partido/UF) e divergência data × data_sessao.
- **Reprodutibilidade:** re-coleta uma janela fixa da API e compara, registro a registro
  (hash dos campos persistidos), com o que está no banco — mede se reexecutar o pipeline
  para o mesmo recorte devolve o mesmo resultado.

Salva um JSON versionável em ``resultados/etl/verificacao_etl.json`` e imprime um resumo.

Uso::

    python3 scripts/verificar_etl.py
    python3 scripts/verificar_etl.py --janela-inicio 2026-05-01 --janela-fim 2026-05-15
    python3 scripts/verificar_etl.py --sem-reprodutibilidade   # offline
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # p/ importar coletar_corpus

from src.data import db
from src.config.constants import SENADO_API_DISCURSOS, SENADO_HEADERS, REQUEST_TIMEOUT
from coletar_corpus import _parse_discursos  # reusa o mesmo parser da coleta

SAIDA_PADRAO = Path("resultados/etl/verificacao_etl.json")

UFS_VALIDAS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
    "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

_CAMPOS_HASH = list(db.COLUNAS_DISCURSO)


def _hash_registro(d: dict) -> str:
    canon = "|".join(f"{c}={(d.get(c) or '').strip()}" for c in _CAMPOS_HASH)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _completude(con) -> dict:
    total = db.contar(con, "discursos")
    essenciais = ["data", "nome_autor", "resumo", "tipo_autor"]
    fill = {}
    for campo in essenciais:
        n = con.execute(
            f"SELECT COUNT(*) FROM discursos WHERE TRIM(COALESCE({campo},'')) <> ''"
        ).fetchone()[0]
        fill[campo] = {"preenchidos": n, "taxa": round(n / total, 4) if total else 0.0}

    completos = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE "
        "TRIM(COALESCE(data,''))<>'' AND TRIM(COALESCE(nome_autor,''))<>'' "
        "AND TRIM(COALESCE(resumo,''))<>'' AND TRIM(COALESCE(tipo_autor,''))<>''"
    ).fetchone()[0]

    sen_total = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%'"
    ).fetchone()[0]
    sen_fill = {}
    for campo in ["partido", "uf"]:
        n = con.execute(
            f"SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%' "
            f"AND TRIM(COALESCE({campo},'')) <> ''"
        ).fetchone()[0]
        sen_fill[campo] = {"preenchidos": n, "taxa": round(n / sen_total, 4) if sen_total else 0.0}

    return {
        "total_discursos": total,
        "campos_essenciais": fill,
        "registros_completos": completos,
        "taxa_completude_geral": round(completos / total, 4) if total else 0.0,
        "senadores_total": sen_total,
        "campos_senador": sen_fill,
    }


def _consistencia(con, hoje: date) -> dict:
    dup_conteudo = con.execute(
        "SELECT COUNT(*) FROM (SELECT resumo, nome_autor, data FROM discursos "
        "WHERE TRIM(COALESCE(resumo,''))<>'' GROUP BY resumo, nome_autor, data HAVING COUNT(*)>1)"
    ).fetchone()[0]

    invalidas = 0
    futuras = 0
    for (d,) in con.execute("SELECT data FROM discursos"):
        try:
            dt = datetime.strptime((d or "").strip(), "%Y-%m-%d").date()
        except ValueError:
            invalidas += 1
            continue
        if dt > hoje:
            futuras += 1
        if dt.year < 2000:
            invalidas += 1

    uf_invalidas = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%' "
        "AND TRIM(COALESCE(uf,''))<>'' AND uf NOT IN ({})".format(
            ",".join("'%s'" % u for u in UFS_VALIDAS)
        )
    ).fetchone()[0]

    sen_sem_partido = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%' "
        "AND TRIM(COALESCE(partido,''))=''"
    ).fetchone()[0]
    sen_sem_uf = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE tipo_autor LIKE 'Senador%' "
        "AND TRIM(COALESCE(uf,''))=''"
    ).fetchone()[0]

    divergencia_sessao = con.execute(
        "SELECT COUNT(*) FROM discursos WHERE TRIM(COALESCE(data,''))<>'' "
        "AND TRIM(COALESCE(data_sessao,''))<>'' AND data <> data_sessao"
    ).fetchone()[0]

    return {
        "duplicatas_codigo": 0,  # garantido pela PK codigo_pronunciamento
        "grupos_duplicata_conteudo": dup_conteudo,
        "datas_invalidas": invalidas,
        "datas_futuras": futuras,
        "uf_invalidas_senador": uf_invalidas,
        "senador_sem_partido": sen_sem_partido,
        "senador_sem_uf": sen_sem_uf,
        "divergencia_data_vs_data_sessao": divergencia_sessao,
    }


def _reprodutibilidade(con, ini: date, fim: date) -> dict:
    """Re-coleta a janela [ini, fim] da API e compara com o banco (hash por registro)."""
    url = f"{SENADO_API_DISCURSOS}/{ini:%Y%m%d}/{fim:%Y%m%d}"
    resp = requests.get(url, headers=SENADO_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    api_regs = {r["codigo_pronunciamento"]: r for r in _parse_discursos(resp.text)}

    rows = con.execute(
        "SELECT * FROM discursos WHERE data BETWEEN ? AND ?",
        (ini.isoformat(), fim.isoformat()),
    ).fetchall()
    db_regs = {r["codigo_pronunciamento"]: dict(r) for r in rows}

    cods_api = set(api_regs)
    cods_db = set(db_regs)
    comuns = cods_api & cods_db
    identicos = sum(1 for c in comuns if _hash_registro(api_regs[c]) == _hash_registro(db_regs[c]))

    return {
        "janela": {"inicio": ini.isoformat(), "fim": fim.isoformat()},
        "n_api": len(cods_api),
        "n_banco_no_periodo": len(cods_db),
        "intersecao": len(comuns),
        "so_na_api": len(cods_api - cods_db),
        "so_no_banco": len(cods_db - cods_api),
        "registros_identicos_no_conteudo": identicos,
        "taxa_reprodutibilidade": round(identicos / len(comuns), 4) if comuns else 0.0,
    }


def _data(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    ap = argparse.ArgumentParser(description="Verificação empírica do ETL (dimensão 4.1).")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--janela-inicio", type=_data, default=_data("2026-05-01"))
    ap.add_argument("--janela-fim", type=_data, default=_data("2026-05-15"))
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--sem-reprodutibilidade", action="store_true",
                    help="Pula a re-coleta da API (útil offline).")
    args = ap.parse_args()

    con = db.conectar(args.db)
    hoje = date.today()

    relatorio = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "banco": args.db,
        "completude": _completude(con),
        "consistencia": _consistencia(con, hoje),
    }
    if args.sem_reprodutibilidade:
        relatorio["reprodutibilidade"] = {"pulado": True}
    else:
        try:
            relatorio["reprodutibilidade"] = _reprodutibilidade(con, args.janela_inicio, args.janela_fim)
        except Exception as e:
            relatorio["reprodutibilidade"] = {"erro": str(e)}
    con.close()

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    c = relatorio["completude"]
    k = relatorio["consistencia"]
    r = relatorio["reprodutibilidade"]
    print("=== DIMENSÃO 4.1 — VERIFICAÇÃO DO ETL ===\n")
    print(f"COMPLETUDE ({c['total_discursos']} discursos)")
    print(f"  completude geral (todos os essenciais): {c['taxa_completude_geral']*100:.2f}%")
    for campo, v in c["campos_essenciais"].items():
        print(f"    {campo:12} {v['taxa']*100:6.2f}%  ({v['preenchidos']})")
    print(f"  senadores ({c['senadores_total']}): "
          f"partido {c['campos_senador']['partido']['taxa']*100:.2f}%, "
          f"uf {c['campos_senador']['uf']['taxa']*100:.2f}%")
    print("\nCONSISTÊNCIA")
    for chave, val in k.items():
        print(f"  {chave:34} {val}")
    print("\nREPRODUTIBILIDADE")
    if "taxa_reprodutibilidade" in r:
        print(f"  janela {r['janela']['inicio']}..{r['janela']['fim']}: "
              f"API={r['n_api']}, banco={r['n_banco_no_periodo']}, interseção={r['intersecao']}")
        print(f"  registros idênticos: {r['registros_identicos_no_conteudo']}/{r['intersecao']} "
              f"→ taxa {r['taxa_reprodutibilidade']*100:.2f}%")
        print(f"  só na API: {r['so_na_api']}   só no banco: {r['so_no_banco']}")
    else:
        print(f"  {r}")
    print(f"\n✅ Salvo em {saida}")


if __name__ == "__main__":
    main()
