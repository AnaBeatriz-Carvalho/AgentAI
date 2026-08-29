"""Pipeline de indexação do RAG.

Recebe o DataFrame de discursos já coletado, busca o **texto integral** de cada pronunciamento
(fallback para o `Resumo` quando indisponível), fatia em chunks, gera embeddings e constrói o
índice FAISS persistido em disco.

Idempotente: reconstrói o índice do zero a partir do DataFrame e sobrescreve os arquivos —
reindexar não duplica trechos.

Uso via CLI (coleta um período recente e indexa):
    python -m src.rag.indexer --dias 7
"""

import argparse

import pandas as pd

from src.config.constants import (
    COL_ID_DISCURSO, COL_DATA, COL_PARLAMENTAR, COL_PARTIDO, COL_UF, COL_RESUMO, COL_TEMA,
)
from src.config.settings import get_rag_config
from src.rag import embedder
from src.rag.chunker import chunk_texto
from src.rag.senado_texto import buscar_texto_integral
from src.rag.vectorstore import VectorStore
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Campos de metadados preservados por chunk — base da citação da fonte.
_CAMPOS_META = [COL_ID_DISCURSO, COL_DATA, COL_PARLAMENTAR, COL_PARTIDO, COL_UF, COL_TEMA]


def _valor_str(valor) -> str:
    """Serializa um valor de célula para string simples (datas viram YYYY-MM-DD)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    if hasattr(valor, "strftime"):  # pandas Timestamp / datetime
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def _meta_do_discurso(row: pd.Series, origem_texto: str) -> dict:
    meta = {campo: _valor_str(row.get(campo)) for campo in _CAMPOS_META if campo in row.index}
    meta["origem_texto"] = origem_texto  # "integral" | "resumo" (auditoria)
    return meta


def indexar_discursos(
    df: pd.DataFrame,
    index_path: str | None = None,
    meta_path: str | None = None,
    buscar_integral: bool = True,
) -> dict:
    """Indexa os discursos do DataFrame e salva o índice FAISS + metadados.

    Retorna estatísticas: nº de discursos, quantos usaram texto integral vs fallback `Resumo`,
    total de chunks e os caminhos gravados.
    """
    cfg = get_rag_config()
    index_path = index_path or cfg["index_path"]
    meta_path = meta_path or cfg["meta_path"]

    stats = {"discursos": 0, "com_integral": 0, "com_fallback": 0, "sem_texto": 0,
             "chunks": 0, "index_path": index_path, "meta_path": meta_path}

    if df is None or df.empty:
        logger.warning("Nenhum discurso para indexar (DataFrame vazio).")
        return stats

    textos_chunks: list[str] = []
    metas_chunks: list[dict] = []

    for _, row in df.iterrows():
        stats["discursos"] += 1
        codigo = _valor_str(row.get(COL_ID_DISCURSO))
        resumo = _valor_str(row.get(COL_RESUMO))

        texto, origem = "", "resumo"
        if buscar_integral and codigo:
            texto = buscar_texto_integral(codigo)
            if texto:
                origem = "integral"
        if not texto:  # fallback: resumo já coletado
            texto = resumo
            origem = "resumo"

        if not texto.strip():
            stats["sem_texto"] += 1
            continue

        stats["com_integral" if origem == "integral" else "com_fallback"] += 1
        meta = _meta_do_discurso(row, origem)
        for chunk in chunk_texto(texto, meta, cfg["chunk_size"], cfg["chunk_overlap"]):
            textos_chunks.append(chunk["texto"])
            metas_chunks.append(chunk["meta"])

    stats["chunks"] = len(textos_chunks)
    if not textos_chunks:
        logger.warning("Nenhum chunk gerado — índice não foi criado.")
        return stats

    logger.info(
        f"Indexando {stats['discursos']} discursos "
        f"({stats['com_integral']} integral, {stats['com_fallback']} resumo) "
        f"-> {stats['chunks']} chunks."
    )
    vetores = embedder.embed(textos_chunks)
    VectorStore().build(vetores, metas_chunks, textos_chunks).save(index_path, meta_path)
    logger.info(f"Índice salvo: {index_path} / {meta_path}")
    return stats


def _coletar_discursos(dias: int) -> pd.DataFrame:
    """Coleta discursos dos últimos `dias` para a indexação via CLI."""
    from datetime import date, timedelta
    from src.data.data_processing import extrair_discursos_senado

    fim = date.today()
    inicio = fim - timedelta(days=dias)
    return extrair_discursos_senado(inicio, fim)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa discursos do Senado no RAG (FAISS).")
    parser.add_argument("--dias", type=int, default=7, help="Janela de coleta (dias). Padrão: 7.")
    parser.add_argument("--sem-integral", action="store_true",
                        help="Não buscar texto integral; indexa apenas o Resumo.")
    args = parser.parse_args()

    df = _coletar_discursos(args.dias)
    stats = indexar_discursos(df, buscar_integral=not args.sem_integral)
    print(
        f"Discursos: {stats['discursos']} | integral: {stats['com_integral']} | "
        f"fallback resumo: {stats['com_fallback']} | sem texto: {stats['sem_texto']} | "
        f"chunks: {stats['chunks']}\n"
        f"Índice: {stats['index_path']}\nMetadados: {stats['meta_path']}"
    )


if __name__ == "__main__":
    main()
