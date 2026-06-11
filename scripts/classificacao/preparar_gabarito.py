"""CLI: gera o template do gabarito ouro para anotacao humana da classificacao tematica.

Le o corpus congelado (`eval/corpus_snapshot.csv`) e produz um CSV com uma linha por
discurso para a pesquisadora preencher a coluna `tema_gold` (anotacao humana = verdade).

ANOTACAO CEGA: o arquivo NAO contem predicoes de nenhum sistema (nem keyword nem Mistral).
Expor a saida de um baseline ao anotador enviesaria o gabarito contra o proprio sistema que
ele vai julgar. `tema_gold` nasce vazio de proposito: o gabarito e anotacao humana
independente.

Saida UTF-8 com BOM (utf-8-sig) para abrir corretamente no Excel no Windows.

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\preparar_gabarito.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.classificacao._comum import (
    GABARITO_TEMPLATE,
    SNAPSHOT_CSV,
    carregar_taxonomia,
    rotulos,
)

_COLS_CONTEXTO = ["id_discurso", "Data", "Parlamentar", "Partido", "UF", "Resumo"]


def main() -> int:
    if not SNAPSHOT_CSV.exists():
        raise SystemExit(f"Corpus congelado nao encontrado: {SNAPSHOT_CSV}")

    df = pd.read_csv(SNAPSHOT_CSV, encoding="utf-8")
    faltando = [c for c in _COLS_CONTEXTO if c not in df.columns]
    if faltando:
        raise SystemExit(f"Snapshot sem colunas obrigatorias: {faltando}")

    tx = carregar_taxonomia()
    out = df[_COLS_CONTEXTO].copy()
    out["tema_gold"] = ""        # anotacao humana (a preencher) — nasce vazio
    out["observacao"] = ""       # casos-limite / duvidas

    GABARITO_TEMPLATE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(GABARITO_TEMPLATE, index=False, encoding="utf-8-sig")

    print(f"Template gerado: {GABARITO_TEMPLATE}")
    print(f"  Discursos: {len(out)}")
    print(f"  Colunas: {list(out.columns)}")
    print(f"  Rotulos validos para 'tema_gold': {rotulos(tx)}")
    print("  Anotacao CEGA: o arquivo NAO contem predicoes de nenhum sistema.")
    print("\nPreencha a coluna 'tema_gold' e salve como eval/classificacao/gabarito.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
