"""CLI: Baseline 2 (classificador supervisionado classico) — TF-IDF + modelo linear.

Termo de comparacao exigente da clausula (a): dimensiona se o ganho do LLM (caso exista)
justifica o custo. Representa o `Resumo` por TF-IDF e treina um classificador linear
(LinearSVC por padrao; Naive Bayes via --modelo nb) por VALIDACAO CRUZADA sobre o proprio
gabarito (`cross_val_predict`, StratifiedKFold). Cada discurso recebe a predicao do fold
em que ficou de fora do treino — predicao out-of-fold comparavel ponto-a-ponto com o
Mistral, o Baseline 1 e o gabarito.

Requer o gabarito anotado: eval/classificacao/gabarito.csv (coluna tema_gold preenchida).

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\baseline_tfidf.py
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\baseline_tfidf.py --modelo nb --folds 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from scripts.classificacao._comum import COL_GOLD, COL_ID, GABARITO_CSV, PRED_TFIDF, rotulo_canonico

# Stopwords PT minimas (alinhadas ao espirito do retrieval do app; nao exaustivas).
_STOPWORDS_PT = [
    "de", "da", "do", "das", "dos", "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "e", "ou", "que", "com", "sem", "por", "para", "em", "no", "na", "nos", "nas",
    "ao", "aos", "se", "sua", "seu", "suas", "seus", "como", "mais", "menos", "sobre",
    "foi", "ser", "sao", "tem", "ter", "destaque", "sessao", "exa", "exas", "sr", "sra",
]


def _construir_modelo(nome: str) -> Pipeline:
    vec = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=2,
        stop_words=_STOPWORDS_PT,
    )
    if nome == "nb":
        clf = MultinomialNB()
    else:
        clf = LinearSVC()  # linear, robusto em texto esparso e amostra pequena
    return Pipeline([("tfidf", vec), ("clf", clf)])


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline 2: TF-IDF + classificador linear (CV).")
    parser.add_argument("--modelo", choices=["svm", "nb"], default="svm")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--saida", type=str, default=str(PRED_TFIDF))
    args = parser.parse_args()

    if not GABARITO_CSV.exists():
        raise SystemExit(
            f"Gabarito nao encontrado: {GABARITO_CSV}\n"
            "Anote o gabarito antes (preencha 'tema_gold' e salve como gabarito.csv)."
        )
    df = pd.read_csv(GABARITO_CSV, encoding="utf-8")
    df = df[df[COL_GOLD].fillna("").str.strip() != ""].copy()
    if df.empty:
        raise SystemExit("Gabarito sem nenhuma linha com 'tema_gold' preenchido.")

    # Normaliza tema_gold para o rotulo canonico (aceita acento/caixa naturais).
    df["_gold"] = df[COL_GOLD].map(rotulo_canonico)
    invalidos = df[df["_gold"].isna()]
    if not invalidos.empty:
        raise SystemExit(
            f"{len(invalidos)} linha(s) com 'tema_gold' invalido (fora dos 5 rotulos). "
            "Rode checar_gabarito.py para localizar e corrigir antes."
        )

    X = df["Resumo"].fillna("").astype(str)
    y = df["_gold"].astype(str)

    # Folds estaveis: nao pode exceder o tamanho da menor classe (StratifiedKFold).
    min_classe = y.value_counts().min()
    folds = max(2, min(args.folds, int(min_classe)))
    if folds < args.folds:
        print(f"[aviso] menor classe tem {min_classe} instancias; reduzindo folds para {folds}.")

    modelo = _construir_modelo(args.modelo)
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    y_pred = cross_val_predict(modelo, X, y, cv=skf)

    out = pd.DataFrame({COL_ID: df[COL_ID].values, "pred_tfidf": y_pred})
    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(saida, index=False, encoding="utf-8-sig")

    print(f"Gabarito: {len(df)} discursos | modelo: TF-IDF + {args.modelo.upper()} | folds: {folds}")
    print(f"Predicoes (out-of-fold) salvas: {saida}")
    print("Distribuicao (Baseline 2):")
    for rot, cont in out["pred_tfidf"].value_counts().items():
        print(f"  {rot}: {cont}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
