"""CLI: congela o snapshot de corpus usado na avaliação comparativa de modelos.

Materializa em disco o DataFrame de discursos que será usado em TODA a avaliação e
serializa os IDs (códigos reais do Senado) num arquivo de texto. Isso fixa o corpus:
modelos testados em dias diferentes passam a ver exatamente os mesmos dados, fechando
a pendência de "corpus versionado não congelado".

Gera:
    eval/corpus_snapshot.csv       — DataFrame congelado (id_discurso, Data, Parlamentar,
                                     Partido, UF, Resumo, Tema)
    eval/corpus_snapshot_ids.txt   — um id_discurso por linha (provenance / versionamento)

Uso:
    # Buscar da API do Senado um período fixo (<= 30 dias) e congelar:
    python scripts/congelar_corpus.py --inicio 20250505 --fim 20250516

    # Ou congelar a partir de um CSV já exportado (não consulta a API):
    python scripts/congelar_corpus.py --from-csv caminho/discursos.csv

O tema é atribuído pela MESMA heurística de palavra-chave do app
(`classificar_tema_local`, determinística, sem LLM), para manter a recuperação por
palavra-chave idêntica à do chat.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.ai.local_llm_handler import classificar_tema_local
from src.config.constants import COL_ID_DISCURSO, TEMAS_DEFINIDOS

EVAL_DIR = ROOT / "eval"
SNAPSHOT_CSV = EVAL_DIR / "corpus_snapshot.csv"
SNAPSHOT_IDS = EVAL_DIR / "corpus_snapshot_ids.txt"

_COLUNAS_SNAPSHOT = [COL_ID_DISCURSO, "Data", "Parlamentar", "Partido", "UF", "Resumo", "Tema"]


def _classificar_tema(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona/atualiza a coluna Tema com a heurística de palavra-chave (sem LLM)."""
    resumos = df["Resumo"].fillna("").tolist()
    df = df.copy()
    df["Tema"] = [classificar_tema_local(r, TEMAS_DEFINIDOS) for r in resumos]
    return df


def _carregar_de_csv(caminho: Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    if COL_ID_DISCURSO not in df.columns or "Resumo" not in df.columns:
        raise SystemExit(
            f"CSV inválido: faltam colunas obrigatórias '{COL_ID_DISCURSO}'/'Resumo'."
        )
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df


def _buscar_da_api(inicio: str, fim: str) -> pd.DataFrame:
    # Import tardio: extrair_discursos_senado importa streamlit/etc.
    from src.data.data_processing import extrair_discursos_senado

    di = datetime.strptime(inicio, "%Y%m%d").date()
    dfim = datetime.strptime(fim, "%Y%m%d").date()
    df = extrair_discursos_senado(di, dfim)
    if df is None or df.empty:
        raise SystemExit(
            "A API do Senado não retornou discursos para o período. "
            "Tente um intervalo com dias úteis."
        )
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Congela o corpus de avaliação.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--from-csv", type=str, help="Congela a partir de um CSV exportado.")
    parser.add_argument("--inicio", type=str, help="Data inicial YYYYMMDD (com --fim).")
    parser.add_argument("--fim", type=str, help="Data final YYYYMMDD (com --inicio).")
    grupo.add_argument(
        "--api", action="store_true",
        help="Busca da API do Senado (requer --inicio e --fim).",
    )
    args = parser.parse_args()

    if args.from_csv:
        df = _carregar_de_csv(Path(args.from_csv))
    else:
        if not (args.inicio and args.fim):
            raise SystemExit("--api exige --inicio e --fim (YYYYMMDD).")
        df = _buscar_da_api(args.inicio, args.fim)

    df = _classificar_tema(df)

    # Garante as colunas esperadas (as ausentes ficam vazias, sem quebrar o retrieval).
    for col in _COLUNAS_SNAPSHOT:
        if col not in df.columns:
            df[col] = ""
    df = df[_COLUNAS_SNAPSHOT]

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOT_CSV, index=False, encoding="utf-8")

    ids = df[COL_ID_DISCURSO].astype(str).tolist()
    SNAPSHOT_IDS.write_text("\n".join(ids) + "\n", encoding="utf-8")

    print(f"Snapshot congelado: {len(df)} discursos")
    print(f"  CSV:  {SNAPSHOT_CSV}")
    print(f"  IDs:  {SNAPSHOT_IDS}")
    print(f"  Temas: {df['Tema'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
