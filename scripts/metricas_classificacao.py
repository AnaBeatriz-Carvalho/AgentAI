"""Métricas de classificação temática — comparação explícita entre modelos (etapa 6).

Para cada classificador (baseline por palavras-chave + cada LLM em ``classificacao_llm``),
calcula, contra o gabarito humano: acurácia, precisão/revocação/F1 por categoria,
macro-F1, weighted-F1, Kappa de Cohen e matriz de confusão. Consolida tudo numa tabela
comparativa modelos×métricas e numa tabela F1-por-categoria×modelos, prontas para o artigo.

Também calcula a **concordância entre os modelos** (agreement + Kappa par-a-par), que roda
mesmo antes de o gabarito estar pronto e mostra o quanto os LLMs divergem entre si.

Saídas versionáveis em ``resultados/metricas/``:
- ``comparativo_modelos.csv`` — uma linha por classificador (acurácia, macro/weighted-F1, kappa).
- ``f1_por_categoria.csv`` — categorias × modelos.
- ``concordancia_entre_modelos.csv`` — pares de modelos (agreement, kappa).
- ``metricas_classificacao.json`` — tudo, incluindo matrizes de confusão.

Uso::

    python3 scripts/metricas_classificacao.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval.categorias import CATEGORIAS, CATEGORIAS_REPORTAVEIS, classificar_keyword
from src.eval import metricas as M

CSV_GABARITO_PADRAO = Path("resultados/gabarito/anotacao_discursos.csv")
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
    """id_discurso → categoria anotada (só linhas com categoria preenchida)."""
    gold = {}
    invalidos = []
    with Path(caminho).open(encoding="utf-8-sig", newline="") as fh:
        for linha in csv.DictReader(fh):
            cat = (linha.get("categoria") or "").strip()
            if not cat:
                continue
            if cat not in CATEGORIAS:
                invalidos.append((linha["id_discurso"], cat))
            gold[linha["id_discurso"]] = cat
    if invalidos:
        print(f"⚠️  {len(invalidos)} rótulos fora da taxonomia (verifique digitação): {invalidos[:5]}")
    return gold


def _predicoes(con, ids: list[str]) -> dict[str, dict[str, str]]:
    """Retorna {classificador: {id: categoria}} para baseline e cada modelo LLM."""
    marc = ",".join("?" * len(ids))
    resumos = {
        r["codigo_pronunciamento"]: (r["resumo"] or "")
        for r in con.execute(
            f"SELECT codigo_pronunciamento, resumo FROM discursos WHERE codigo_pronunciamento IN ({marc})",
            ids,
        )
    }
    preds: dict[str, dict[str, str]] = {
        "Baseline-KW": {i: classificar_keyword(resumos.get(i, "")) for i in ids}
    }
    for row in con.execute("SELECT DISTINCT modelo FROM classificacao_llm"):
        modelo = row["modelo"]
        mp = {
            r["id_discurso"]: r["categoria"]
            for r in con.execute(
                "SELECT id_discurso, categoria FROM classificacao_llm WHERE modelo=?", (modelo,)
            )
        }
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
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--gabarito", default=str(CSV_GABARITO_PADRAO))
    ap.add_argument("--saida", default=str(DIR_SAIDA_PADRAO))
    args = ap.parse_args()

    con = db.conectar(args.db)
    con.row_factory = __import__("sqlite3").Row

    # ids = todos do CSV de anotação (base do gabarito).
    with Path(args.gabarito).open(encoding="utf-8-sig", newline="") as fh:
        ids = [l["id_discurso"] for l in csv.DictReader(fh)]

    preds = _predicoes(con, ids)
    gold_map = _carregar_gabarito(args.gabarito)
    con.close()

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
    if not gold_map:
        print("\n⚠️  Gabarito ainda não preenchido (coluna 'categoria' vazia). "
              "As métricas contra o gabarito rodarão quando a anotação estiver pronta.")
        (saida / "metricas_classificacao.json").write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n✅ Concordância entre modelos salva em {saida}")
        return

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
