"""CLI: metricas comparativas da classificacao tematica (clausula (a)).

Consolida gabarito + predicoes (Mistral, Baseline 1 keyword, Baseline 2 TF-IDF) e calcula:
  - acuracia, precisao, revocacao e F1 (por classe e macro/weighted) por sistema;
  - intervalos de confianca por BOOTSTRAP (percentil) para acuracia e F1-macro;
  - IC bootstrap da DIFERENCA (Mistral - baseline), pareado — descritivo, SEM teste de
    significancia (o desenho nao comporta; declarar como tal);
  - matriz de confusao por sistema;
  - exportacao dos casos de erro (para a analise qualitativa).

O bootstrap reamostra as instancias do gabarito (com reposicao); seu random_state e fixo,
entao ESTA parte e reproducivel (ao contrario da geracao do LLM). Saidas em
eval/classificacao/resultados/.

Requer: gabarito.csv (tema_gold) + ao menos um pred_*.csv. Sistemas ausentes sao pulados.

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\metricas.py
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\metricas.py --bootstrap 5000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

from scripts.classificacao._comum import (
    CLASSIF_DIR,
    COL_GOLD,
    COL_ID,
    GABARITO_CSV,
    PRED_KEYWORD,
    PRED_MISTRAL,
    PRED_TFIDF,
    rotulo_canonico,
    rotulos,
)

RESULT_DIR = CLASSIF_DIR / "resultados"

# (nome do sistema, caminho do pred, nome da coluna de predicao)
SISTEMAS = [
    ("mistral", PRED_MISTRAL, "pred_mistral"),
    ("keyword", PRED_KEYWORD, "pred_keyword"),
    ("tfidf", PRED_TFIDF, "pred_tfidf"),
]


def _carregar_alinhado(gabarito: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Para cada sistema disponivel, junta gold+pred por id_discurso (so ids do gabarito)."""
    base = gabarito[[COL_ID, COL_GOLD]].copy()
    disponiveis: dict[str, pd.DataFrame] = {}
    for nome, caminho, col in SISTEMAS:
        if not caminho.exists():
            print(f"[pulado] {nome}: {caminho.name} ausente.")
            continue
        pred = pd.read_csv(caminho, encoding="utf-8")[[COL_ID, col]]
        merged = base.merge(pred, on=COL_ID, how="inner").dropna(subset=[COL_GOLD, col])
        merged = merged[merged[COL_GOLD].astype(str).str.strip() != ""]
        if merged.empty:
            print(f"[pulado] {nome}: sem linhas alinhadas com o gabarito.")
            continue
        disponiveis[nome] = merged.rename(columns={col: "pred"})
        print(f"[ok] {nome}: {len(merged)} instancias alinhadas.")
    return disponiveis


def _metricas_agregadas(y_true, y_pred, labels) -> dict:
    acc = accuracy_score(y_true, y_pred)
    f1_macro = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    f1_weighted = f1_score(y_true, y_pred, labels=labels, average="weighted", zero_division=0)
    p_macro, r_macro, _, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    return {
        "acuracia": acc,
        "precisao_macro": p_macro,
        "revocacao_macro": r_macro,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
    }


def _relatorio_por_classe(y_true, y_pred, labels) -> pd.DataFrame:
    p, r, f1, sup = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    return pd.DataFrame({
        "classe": labels, "precisao": p, "revocacao": r, "f1": f1, "suporte": sup,
    })


def _bootstrap_ic(y_true, y_pred, labels, b: int, rng) -> dict:
    """IC percentil (2.5/97.5) de acuracia e F1-macro por reamostragem das instancias."""
    n = len(y_true)
    yt = np.asarray(y_true)
    yp = np.asarray(y_pred)
    accs, f1s = np.empty(b), np.empty(b)
    for i in range(b):
        idx = rng.integers(0, n, n)
        accs[i] = accuracy_score(yt[idx], yp[idx])
        f1s[i] = f1_score(yt[idx], yp[idx], labels=labels, average="macro", zero_division=0)
    return {
        "acuracia_ic95": (float(np.percentile(accs, 2.5)), float(np.percentile(accs, 97.5))),
        "f1_macro_ic95": (float(np.percentile(f1s, 2.5)), float(np.percentile(f1s, 97.5))),
    }


def _bootstrap_diferenca(y_true, pred_a, pred_b, labels, b: int, rng) -> dict:
    """IC pareado da diferenca (A - B) em acuracia/F1-macro. DESCRITIVO, sem significancia."""
    n = len(y_true)
    yt = np.asarray(y_true)
    pa = np.asarray(pred_a)
    pb = np.asarray(pred_b)
    d_acc, d_f1 = np.empty(b), np.empty(b)
    for i in range(b):
        idx = rng.integers(0, n, n)
        yti = yt[idx]
        d_acc[i] = accuracy_score(yti, pa[idx]) - accuracy_score(yti, pb[idx])
        d_f1[i] = (f1_score(yti, pa[idx], labels=labels, average="macro", zero_division=0)
                   - f1_score(yti, pb[idx], labels=labels, average="macro", zero_division=0))
    return {
        "d_acuracia": float(np.mean(d_acc)),
        "d_acuracia_ic95": (float(np.percentile(d_acc, 2.5)), float(np.percentile(d_acc, 97.5))),
        "d_f1_macro": float(np.mean(d_f1)),
        "d_f1_macro_ic95": (float(np.percentile(d_f1, 2.5)), float(np.percentile(d_f1, 97.5))),
    }


def _fmt_ic(par: tuple[float, float]) -> str:
    return f"[{par[0]:.3f}, {par[1]:.3f}]"


def main() -> int:
    parser = argparse.ArgumentParser(description="Metricas comparativas da classificacao tematica.")
    parser.add_argument("--bootstrap", type=int, default=2000, help="Reamostragens (default 2000).")
    parser.add_argument("--seed", type=int, default=42, help="random_state do bootstrap.")
    args = parser.parse_args()

    if not GABARITO_CSV.exists():
        raise SystemExit(f"Gabarito nao encontrado: {GABARITO_CSV}")
    gabarito = pd.read_csv(GABARITO_CSV, encoding="utf-8")
    if COL_GOLD not in gabarito.columns:
        raise SystemExit(f"Coluna '{COL_GOLD}' ausente no gabarito.")
    # Normaliza o gabarito para o rotulo canonico (aceita acento/caixa naturais). As
    # predicoes (pred_*) ja sao canonicas, geradas pelo codigo.
    gabarito[COL_GOLD] = gabarito[COL_GOLD].map(rotulo_canonico)

    sistemas = _carregar_alinhado(gabarito)
    if not sistemas:
        raise SystemExit("Nenhum sistema com predicoes disponiveis. Rode os scripts de predicao antes.")

    labels = rotulos()
    rng = np.random.default_rng(args.seed)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Tabela consolidada (1 linha por sistema) ---
    linhas_resumo = []
    for nome, dfm in sistemas.items():
        yt, yp = dfm[COL_GOLD].tolist(), dfm["pred"].tolist()
        agg = _metricas_agregadas(yt, yp, labels)
        ic = _bootstrap_ic(yt, yp, labels, args.bootstrap, rng)
        linhas_resumo.append({
            "sistema": nome,
            "n": len(dfm),
            **{k: round(v, 4) for k, v in agg.items()},
            "acuracia_ic95": _fmt_ic(ic["acuracia_ic95"]),
            "f1_macro_ic95": _fmt_ic(ic["f1_macro_ic95"]),
        })
        # por classe
        _relatorio_por_classe(yt, yp, labels).to_csv(
            RESULT_DIR / f"por_classe_{nome}.csv", index=False, encoding="utf-8-sig"
        )
        # matriz de confusao
        cm = confusion_matrix(yt, yp, labels=labels)
        pd.DataFrame(cm, index=labels, columns=labels).to_csv(
            RESULT_DIR / f"confusao_{nome}.csv", encoding="utf-8-sig"
        )

    resumo = pd.DataFrame(linhas_resumo)
    resumo.to_csv(RESULT_DIR / "resumo_metricas.csv", index=False, encoding="utf-8-sig")

    # --- Diferencas Mistral - baseline (IC pareado, descritivo) ---
    linhas_dif = []
    if "mistral" in sistemas:
        m = sistemas["mistral"]
        for base_nome in ("keyword", "tfidf"):
            if base_nome not in sistemas:
                continue
            # alinhar os dois sistemas pelos ids comuns (Mistral roda no snapshot/gabarito;
            # tfidf so existe para linhas anotadas) -> intersecao garante pareamento.
            par = m.merge(
                sistemas[base_nome][[COL_ID, "pred"]], on=COL_ID, suffixes=("_m", "_b")
            )
            if par.empty:
                continue
            dif = _bootstrap_diferenca(
                par[COL_GOLD].tolist(), par["pred_m"].tolist(), par["pred_b"].tolist(),
                labels, args.bootstrap, rng,
            )
            linhas_dif.append({
                "comparacao": f"mistral - {base_nome}",
                "n_pareado": len(par),
                "d_acuracia": round(dif["d_acuracia"], 4),
                "d_acuracia_ic95": _fmt_ic(dif["d_acuracia_ic95"]),
                "d_f1_macro": round(dif["d_f1_macro"], 4),
                "d_f1_macro_ic95": _fmt_ic(dif["d_f1_macro_ic95"]),
            })
    if linhas_dif:
        pd.DataFrame(linhas_dif).to_csv(
            RESULT_DIR / "diferencas_bootstrap.csv", index=False, encoding="utf-8-sig"
        )

    # --- Casos de erro (analise qualitativa) ---
    resumo_txt = gabarito[[COL_ID, "Resumo"]] if "Resumo" in gabarito.columns else gabarito[[COL_ID]]
    erros = gabarito[[COL_ID, COL_GOLD]].copy()
    for nome, dfm in sistemas.items():
        erros = erros.merge(dfm[[COL_ID, "pred"]].rename(columns={"pred": f"pred_{nome}"}),
                            on=COL_ID, how="left")
    erros = erros.merge(resumo_txt, on=COL_ID, how="left")
    cols_pred = [f"pred_{n}" for n in sistemas]
    mask_erro = pd.Series(False, index=erros.index)
    for c in cols_pred:
        mask_erro |= (erros[c].notna() & (erros[c] != erros[COL_GOLD]))
    erros[mask_erro].to_csv(RESULT_DIR / "casos_erro.csv", index=False, encoding="utf-8-sig")

    # --- Console ---
    print("\n=== RESUMO (acuracia / F1-macro com IC95 bootstrap) ===")
    for r in linhas_resumo:
        print(f"  {r['sistema']:>8} | n={r['n']:>3} | acc={r['acuracia']:.3f} "
              f"{r['acuracia_ic95']} | F1m={r['f1_macro']:.3f} {r['f1_macro_ic95']}")
    if linhas_dif:
        print("\n=== DIFERENCAS (Mistral - baseline; IC95 pareado, DESCRITIVO, sem significancia) ===")
        for d in linhas_dif:
            print(f"  {d['comparacao']:>18} | d_acc={d['d_acuracia']:+.3f} {d['d_acuracia_ic95']} "
                  f"| d_F1m={d['d_f1_macro']:+.3f} {d['d_f1_macro_ic95']}")
    print(f"\nArtefatos em: {RESULT_DIR}")
    print("  resumo_metricas.csv, por_classe_*.csv, confusao_*.csv, "
          "diferencas_bootstrap.csv, casos_erro.csv")
    print("\nLembrete metodologico: ICs sao DESCRITIVOS; sem teste de significancia formal; "
          "amostra de 152 e restricao assumida; anotador unico e limitacao declarada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
