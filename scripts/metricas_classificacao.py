"""Métricas de classificação temática — comparação explícita entre modelos (etapa 6).

Para cada classificador (baseline por palavras-chave + cada LLM em ``classificacao_llm``),
calcula, contra o gabarito humano: acurácia, precisão/revocação/F1 por categoria,
macro-F1, weighted-F1, Kappa de Cohen e matriz de confusão. Consolida tudo numa tabela
comparativa modelos×métricas e numa tabela F1-por-categoria×modelos, prontas para o artigo.

Também calcula a **concordância entre os modelos** (agreement + Kappa par-a-par), que
mostra o quanto os LLMs divergem entre si — independentemente do gabarito.

Fontes de dados (padrão, sem SQLite nem rede):
- **Predições dos modelos:** lidas do CSV versionado ``resultados/metricas/predicoes_classificacao_llm.csv``
  (``--predicoes``). O SQLite ``classificacao_llm`` é fonte opcional, só com ``--fonte sqlite``.
- **Gabarito:** por padrão o CSV JÁ ANOTADO ``resultados/gabarito/anotacao_discursos_categorizado.csv``
  (``--gabarito``); o ``resumo`` para o baseline sai do próprio gabarito.

Se o gabarito não tiver a coluna ``categoria`` ou vier sem nenhuma categoria preenchida
(ex.: o formulário de anotação em branco), o script **aborta com erro** — nunca calcula
parcial nem pula em silêncio.

Saídas versionáveis em ``resultados/metricas/``:
- ``comparativo_modelos.csv`` — uma linha por classificador (acurácia, macro/weighted-F1, kappa).
- ``f1_por_categoria.csv`` — categorias × modelos.
- ``concordancia_entre_modelos.csv`` — pares de modelos (agreement, kappa).
- ``metricas_classificacao.json`` — tudo, incluindo matrizes de confusão.

Uso::

    python3 scripts/metricas_classificacao.py                 # CSV versionado + gabarito anotado
    python3 scripts/metricas_classificacao.py --fonte sqlite  # lê predições do SQLite
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval.categorias import CATEGORIAS, CATEGORIAS_REPORTAVEIS, classificar_keyword
from src.eval import metricas as M

# Gabarito canônico: a amostra JÁ ANOTADA (categoria preenchida). O CSV sem categorias
# (anotacao_discursos.csv) é apenas o formulário de anotação e não serve de gabarito aqui.
CSV_GABARITO_PADRAO = Path("resultados/gabarito/anotacao_discursos_categorizado.csv")
# Predições dos modelos versionadas (exportadas da tabela classificacao_llm), para reproduzir
# as métricas sem depender do SQLite gitignorado. O SQLite fica como fonte opcional.
CSV_PREDICOES_PADRAO = Path("resultados/metricas/predicoes_classificacao_llm.csv")
DIR_SAIDA_PADRAO = Path("resultados/metricas")

# Aliases curtos para os ids de modelo do LM Studio (colunas mais limpas no artigo).
ALIASES = {
    "mistralai/mistral-7b-instruct-v0.3": "Mistral-7B",
    "gemma-2-9b-it": "Gemma-2-9B",
    "meta-llama-3.1-8b-instruct": "Llama-3.1-8B",
}


def _alias(modelo: str) -> str:
    return ALIASES.get(modelo, modelo)


def _carregar_gabarito(caminho: Path) -> dict[str, str]:
    """id_discurso → categoria anotada (só linhas com categoria preenchida).

    Aborta (nunca pula em silêncio) se o CSV não tiver a coluna ``categoria`` ou se ela
    estiver totalmente vazia — sinal de que foi passado o formulário de anotação em vez
    do gabarito anotado.
    """
    gold = {}
    invalidos = []
    with Path(caminho).open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.DictReader(fh)
        if leitor.fieldnames is None or "categoria" not in leitor.fieldnames:
            sys.exit(
                f"Gabarito sem coluna 'categoria': {caminho}. Use o gabarito anotado "
                f"(ex.: resultados/gabarito/anotacao_discursos_categorizado.csv)."
            )
        for linha in leitor:
            cat = (linha.get("categoria") or "").strip()
            if not cat:
                continue
            if cat not in CATEGORIAS:
                invalidos.append((linha["id_discurso"], cat))
            gold[linha["id_discurso"]] = cat
    if not gold:
        sys.exit(
            f"Gabarito sem categorias preenchidas: {caminho}. Use o gabarito anotado "
            f"(ex.: resultados/gabarito/anotacao_discursos_categorizado.csv)."
        )
    if invalidos:
        print(f"⚠️  {len(invalidos)} rótulos fora da taxonomia (verifique digitação): {invalidos[:5]}")
    return gold


def _ids_e_resumos(caminho: Path) -> tuple[list[str], dict[str, str]]:
    """Lê o gabarito e devolve (ids na ordem do CSV, {id: resumo}).

    O ``resumo`` sai do próprio gabarito — mesmo texto persistido no SQLite —, de modo
    que o baseline por palavras-chave é recomputável sem abrir o banco.
    """
    ids: list[str] = []
    resumos: dict[str, str] = {}
    with Path(caminho).open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            i = linha["id_discurso"]
            ids.append(i)
            resumos[i] = linha.get("resumo") or ""
    return ids, resumos


def _llm_preds_csv(caminho: Path) -> dict[str, dict[str, str]]:
    """Lê as predições versionadas: {modelo_bruto: {id: categoria}}."""
    out: dict[str, dict[str, str]] = {}
    with Path(caminho).open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            out.setdefault(linha["modelo"], {})[linha["id_discurso"]] = linha["categoria"]
    return out


def _llm_preds_sqlite(con) -> dict[str, dict[str, str]]:
    """Lê as predições da tabela ``classificacao_llm``: {modelo_bruto: {id: categoria}}."""
    out: dict[str, dict[str, str]] = {}
    for row in con.execute("SELECT DISTINCT modelo FROM classificacao_llm"):
        modelo = row["modelo"]
        out[modelo] = {
            r["id_discurso"]: r["categoria"]
            for r in con.execute(
                "SELECT id_discurso, categoria FROM classificacao_llm WHERE modelo=?", (modelo,)
            )
        }
    return out


def _predicoes(
    resumos: dict[str, str],
    llm_por_modelo: dict[str, dict[str, str]],
    ids: list[str],
) -> dict[str, dict[str, str]]:
    """Monta {classificador: {id: categoria}} para o baseline + cada modelo LLM.

    Modelos ordenados pelo id bruto (determinístico, independe da fonte CSV/SQLite).
    """
    preds: dict[str, dict[str, str]] = {
        "Baseline-KW": {i: classificar_keyword(resumos.get(i, "")) for i in ids}
    }
    for modelo in sorted(llm_por_modelo):
        mp = llm_por_modelo[modelo]
        preds[_alias(modelo)] = {i: mp.get(i) for i in ids if i in mp}
    return preds


def _concordancia_entre_modelos(preds: dict[str, dict[str, str]]) -> list[dict]:
    """Agreement + Kappa par-a-par entre classificadores (não usa gabarito)."""
    nomes = list(preds.keys())
    linhas = []
    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            a_nome, b_nome = nomes[i], nomes[j]
            ids_comuns = [x for x in preds[a_nome] if x in preds[b_nome]
                          and preds[a_nome][x] is not None and preds[b_nome][x] is not None]
            a = [preds[a_nome][x] for x in ids_comuns]
            b = [preds[b_nome][x] for x in ids_comuns]
            linhas.append({
                "modelo_a": a_nome,
                "modelo_b": b_nome,
                "n": len(ids_comuns),
                "agreement": M.concordancia_simples(a, b),
                "kappa": M.cohen_kappa(a, b, CATEGORIAS),
            })
    return linhas


def main() -> None:
    ap = argparse.ArgumentParser(description="Métricas de classificação (comparação entre modelos).")
    ap.add_argument("--gabarito", default=str(CSV_GABARITO_PADRAO))
    ap.add_argument("--predicoes", default=str(CSV_PREDICOES_PADRAO),
                    help="CSV com as predições dos modelos (fonte padrão).")
    ap.add_argument("--fonte", choices=["csv", "sqlite"], default="csv",
                    help="De onde ler as predições dos modelos (padrão: csv).")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO),
                    help="Banco SQLite — usado apenas com --fonte sqlite.")
    ap.add_argument("--saida", default=str(DIR_SAIDA_PADRAO))
    args = ap.parse_args()

    # Gabarito primeiro: aborta cedo (sem gerar saída parcial) se não estiver anotado.
    gold_map = _carregar_gabarito(args.gabarito)
    ids, resumos = _ids_e_resumos(args.gabarito)

    # Predições dos modelos: CSV versionado por padrão; SQLite só sob demanda.
    if args.fonte == "sqlite":
        con = db.conectar(args.db)
        con.row_factory = sqlite3.Row
        llm_por_modelo = _llm_preds_sqlite(con)
        con.close()
    else:
        llm_por_modelo = _llm_preds_csv(args.predicoes)

    preds = _predicoes(resumos, llm_por_modelo, ids)

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)

    relatorio: dict = {"n_anotados": len(gold_map), "n_amostra": len(ids), "classificadores": {}}

    # --- Concordância entre modelos (sempre roda) ---
    inter = _concordancia_entre_modelos(preds)
    relatorio["concordancia_entre_modelos"] = inter
    with (saida / "concordancia_entre_modelos.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["modelo_a", "modelo_b", "n", "agreement", "kappa"])
        w.writeheader()
        w.writerows(inter)

    print("=== CONCORDÂNCIA ENTRE MODELOS (independe do gabarito) ===")
    for l in inter:
        print(f"  {l['modelo_a']:14} × {l['modelo_b']:14} n={l['n']:3}  "
              f"agreement={l['agreement']*100:5.1f}%  kappa={l['kappa']}")

    # --- Métricas contra o gabarito ---
    # (o gabarito já foi validado no início — _carregar_gabarito aborta se estiver vazio.)
    gold_ids = list(gold_map.keys())
    comparativo = []
    for nome, mp in preds.items():
        ids_val = [i for i in gold_ids if mp.get(i) is not None]
        gold = [gold_map[i] for i in ids_val]
        pred = [mp[i] for i in ids_val]
        met = M.metricas_por_categoria(gold, pred, CATEGORIAS)
        met["kappa_vs_gabarito"] = M.cohen_kappa(gold, pred, CATEGORIAS)
        met["matriz_confusao"] = M.matriz_confusao(gold, pred, CATEGORIAS)
        # macro-F1 restrito às 8 reportáveis (o número de headline do artigo).
        macro8 = sum(met["por_categoria"][c]["f1"] for c in CATEGORIAS_REPORTAVEIS) / len(CATEGORIAS_REPORTAVEIS)
        met["macro_f1_reportaveis"] = round(macro8, 4)
        relatorio["classificadores"][nome] = met
        comparativo.append({
            "modelo": nome, "n": met["n"], "acuracia": met["acuracia"],
            "macro_f1": met["macro_f1"], "macro_f1_reportaveis": met["macro_f1_reportaveis"],
            "weighted_f1": met["weighted_f1"], "kappa_vs_gabarito": met["kappa_vs_gabarito"],
        })

    comparativo.sort(key=lambda r: r["macro_f1_reportaveis"], reverse=True)
    with (saida / "comparativo_modelos.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(comparativo[0].keys()))
        w.writeheader()
        w.writerows(comparativo)

    # Tabela F1 por categoria × modelos.
    nomes = [c["modelo"] for c in comparativo]
    with (saida / "f1_por_categoria.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["categoria", "suporte"] + nomes)
        for cat in CATEGORIAS:
            sup = next(iter(relatorio["classificadores"].values()))["por_categoria"][cat]["suporte"]
            w.writerow([cat, sup] + [relatorio["classificadores"][n]["por_categoria"][cat]["f1"] for n in nomes])

    (saida / "metricas_classificacao.json").write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== COMPARATIVO (contra gabarito, n_anotados={len(gold_map)}) ===")
    print(f"  {'modelo':14} {'acur':>6} {'macroF1':>8} {'macroF1_8':>10} {'wF1':>6} {'kappa':>6}")
    for r in comparativo:
        print(f"  {r['modelo']:14} {r['acuracia']*100:5.1f}% {r['macro_f1']:8.3f} "
              f"{r['macro_f1_reportaveis']:10.3f} {r['weighted_f1']:6.3f} {r['kappa_vs_gabarito']:6.3f}")
    print(f"\n✅ Métricas salvas em {saida}/")


if __name__ == "__main__":
    main()
