"""CLI: Baseline 1 (correspondencia por palavra-chave) — piso minimo, sem aprendizado.

Aplica o dicionario de palavras-chave por rotulo (em `taxonomia.json`) ao `Resumo` de
cada discurso e atribui o rotulo com mais correspondencias (empate zero -> Outros).
Deterministico e independente do gabarito (nao "treina" em nada).

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\baseline_keyword.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.classificacao._comum import (
    COL_ID,
    GABARITO_CSV,
    PRED_KEYWORD,
    SNAPSHOT_CSV,
    carregar_taxonomia,
    classificar_keyword,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline 1: classificacao por palavra-chave.")
    parser.add_argument("--fonte", choices=["gabarito", "snapshot"], default="gabarito")
    parser.add_argument("--saida", type=str, default=str(PRED_KEYWORD))
    args = parser.parse_args()

    fonte = GABARITO_CSV if (args.fonte == "gabarito" and GABARITO_CSV.exists()) else SNAPSHOT_CSV
    if not fonte.exists():
        raise SystemExit(f"Fonte de discursos nao encontrada: {fonte}")
    df = pd.read_csv(fonte, encoding="utf-8")

    tx = carregar_taxonomia()
    out = pd.DataFrame({
        COL_ID: df[COL_ID],
        "pred_keyword": [classificar_keyword(r, tx) for r in df["Resumo"].fillna("")],
    })

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(saida, index=False, encoding="utf-8-sig")

    print(f"Fonte: {fonte.name} | discursos: {len(df)}")
    print(f"Predicoes salvas: {saida}")
    print("Distribuicao (Baseline 1 - keyword):")
    for rot, cont in out["pred_keyword"].value_counts().items():
        print(f"  {rot}: {cont}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
