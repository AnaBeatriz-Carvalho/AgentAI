"""Gera embeddings (vetores) dos textos para busca semântica.

O modelo é carregado UMA vez (cache de processo) e roda em CPU. Os vetores saem
**normalizados** (norma L2 = 1), para que o produto interno usado pelo FAISS `IndexFlatIP`
seja equivalente à similaridade de cosseno.

`sentence-transformers` (e o PyTorch que ele puxa) é importado de forma preguiçosa, dentro do
loader — assim importar este módulo não exige o peso instalado, o que mantém os testes de
chunking/vectorstore leves e permite monkeypatch nos testes de retrieval.
"""

from functools import lru_cache

import numpy as np

from src.config.settings import get_rag_config
from src.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    """Carrega e memoiza o SentenceTransformer (import preguiçoso do peso)."""
    from sentence_transformers import SentenceTransformer

    logger.info(f"Carregando modelo de embedding: {model_name} (CPU)")
    return SentenceTransformer(model_name, device="cpu")


def embed(textos: list[str], model_name: str | None = None) -> np.ndarray:
    """Transforma uma lista de textos em uma matriz (n, dim) float32 normalizada.

    Lista vazia -> array vazio de shape (0, 0). O nome do modelo vem do `.env`
    (`RAG_EMBEDDING_MODEL`) quando não informado explicitamente.
    """
    if not textos:
        return np.zeros((0, 0), dtype=np.float32)

    model_name = model_name or get_rag_config()["embedding_model"]
    model = _load_model(model_name)
    vetores = model.encode(
        textos,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vetores, dtype=np.float32)


def embed_query(pergunta: str, model_name: str | None = None) -> np.ndarray:
    """Embedding de uma única pergunta -> vetor 1D (dim,) float32 normalizado."""
    matriz = embed([pergunta], model_name=model_name)
    return matriz[0] if len(matriz) else matriz
