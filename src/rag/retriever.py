"""Recupera os trechos mais relevantes à pergunta e monta o contexto com citações.

Devolve as fontes na MESMA forma usada pelo chat existente (ref curto `D1, D2…` + metadados
do discurso), para reaproveitar o prompt, o expander de fontes na UI e o `_registrar_trace`
de rastreabilidade — sem duplicar lógica.

O índice é carregado sob demanda e mantido em cache por caminho + mtime, de modo que uma
reindexação (arquivo mais novo) é detectada e recarregada automaticamente.
"""

import os

from src.config.constants import (
    COL_ID_DISCURSO, COL_DATA, COL_PARLAMENTAR, COL_PARTIDO, COL_UF, COL_TEMA,
    MAX_CHARS_CONTEXTO_PROMPT,
)
from src.config.settings import get_rag_config
from src.rag import embedder
from src.rag.vectorstore import VectorStore
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache de índice: (index_path, meta_path) -> (mtime_index, mtime_meta, VectorStore)
_STORE_CACHE: dict = {}


def _carregar_store(index_path: str, meta_path: str) -> VectorStore | None:
    """Carrega o VectorStore do disco, reusando o cache se os arquivos não mudaram."""
    if not VectorStore.exists(index_path, meta_path):
        return None
    chave = (index_path, meta_path)
    mi, mm = os.path.getmtime(index_path), os.path.getmtime(meta_path)
    cache = _STORE_CACHE.get(chave)
    if cache and cache[0] == mi and cache[1] == mm:
        return cache[2]
    vs = VectorStore.load(index_path, meta_path)
    _STORE_CACHE[chave] = (mi, mm, vs)
    logger.info(f"Índice RAG carregado: {len(vs.textos)} trechos de {index_path}")
    return vs


def _citacao(meta: dict) -> str:
    """Monta o rótulo de citação legível: 'Senador Fulano (PARTIDO), 2025-03-12'."""
    nome = meta.get(COL_PARLAMENTAR, "") or "Autor não identificado"
    partido = meta.get(COL_PARTIDO, "")
    data = meta.get(COL_DATA, "")
    partido_txt = f" ({partido})" if partido else ""
    data_txt = f", {data}" if data else ""
    return f"{nome}{partido_txt}{data_txt}"


def recuperar(pergunta: str, k: int | None = None) -> tuple[str, list[dict]]:
    """Retorna `(contexto_str, fontes)` para a pergunta.

    - `contexto_str`: bloco pronto para o prompt, cada trecho prefixado por um ref citável
      (`[D1]`) e sua citação (senador, partido, data). Cortado em `MAX_CHARS_CONTEXTO_PROMPT`.
    - `fontes`: lista de dicts com `ref`, metadados do discurso, `score` e `trecho`.

    Se não houver índice ou resultados, devolve `("", [])`.
    """
    cfg = get_rag_config()
    k = k or cfg["top_k"]
    store = _carregar_store(cfg["index_path"], cfg["meta_path"])
    if store is None:
        logger.info("Nenhum índice RAG encontrado ao recuperar.")
        return "", []

    vetor = embedder.embed_query(pergunta, model_name=cfg["embedding_model"])
    resultados = store.search(vetor, k)
    if not resultados:
        return "", []

    fontes: list[dict] = []
    linhas: list[str] = []
    for i, (score, meta, texto) in enumerate(resultados):
        ref = f"D{i + 1}"
        fontes.append({
            "ref": ref,
            COL_ID_DISCURSO: meta.get(COL_ID_DISCURSO, ""),
            COL_DATA: meta.get(COL_DATA, ""),
            COL_PARLAMENTAR: meta.get(COL_PARLAMENTAR, ""),
            COL_PARTIDO: meta.get(COL_PARTIDO, ""),
            COL_UF: meta.get(COL_UF, ""),
            COL_TEMA: meta.get(COL_TEMA, ""),
            "score": round(float(score), 4),
            "trecho": texto,
        })
        linhas.append(f'[{ref}] {_citacao(meta)}: "{texto}"')

    contexto = "\n\n".join(linhas)[:MAX_CHARS_CONTEXTO_PROMPT]
    return contexto, fontes
