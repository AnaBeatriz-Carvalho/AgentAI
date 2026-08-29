"""Banco vetorial FAISS (`IndexFlatIP`) com metadados alinhados por posição.

`IndexFlatIP` faz busca exata por produto interno; com vetores normalizados (ver embedder),
isso equivale à similaridade de cosseno. Para coleções de até dezenas de milhares de trechos
é instantâneo e não precisa de servidor.

Persistência em dois arquivos irmãos:
  - `<index_path>`  -> índice FAISS (binário)
  - `<meta_path>`   -> parquet com uma linha por vetor: `meta_json` (metadados) + `texto`,
                       na MESMA ordem em que os vetores foram adicionados ao índice.

`faiss` é importado de forma preguiçosa para não pesar em quem só importa o módulo.
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Encapsula o índice FAISS + textos/metadados alinhados por posição."""

    def __init__(self, index=None, metas: Optional[list[dict]] = None,
                 textos: Optional[list[str]] = None):
        self.index = index
        self.metas: list[dict] = metas or []
        self.textos: list[str] = textos or []

    # ---- construção ----
    def build(self, vetores: np.ndarray, metas: list[dict], textos: list[str]) -> "VectorStore":
        """Constrói o índice a partir de vetores (n, dim) e listas alinhadas de meta/texto."""
        import faiss

        vetores = np.asarray(vetores, dtype=np.float32)
        if vetores.ndim != 2 or vetores.shape[0] == 0:
            raise ValueError("vetores deve ser uma matriz 2D não vazia (n, dim)")
        if not (len(metas) == len(textos) == vetores.shape[0]):
            raise ValueError("vetores, metas e textos devem ter o mesmo comprimento")

        index = faiss.IndexFlatIP(vetores.shape[1])
        index.add(vetores)
        self.index = index
        self.metas = list(metas)
        self.textos = list(textos)
        logger.info(f"Índice FAISS construído: {vetores.shape[0]} vetores, dim={vetores.shape[1]}")
        return self

    # ---- persistência ----
    def save(self, index_path: str, meta_path: str) -> None:
        """Grava o índice FAISS e o parquet de metadados (cria diretórios se preciso)."""
        import faiss

        if self.index is None:
            raise ValueError("Nada a salvar: índice não construído.")
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(meta_path).parent.mkdir(parents=True, exist_ok=True)

        faiss.write_index(self.index, str(index_path))
        df = pd.DataFrame({
            "meta_json": [json.dumps(m, ensure_ascii=False) for m in self.metas],
            "texto": self.textos,
        })
        df.to_parquet(meta_path, index=False)
        logger.info(f"Índice salvo em {index_path} e metadados em {meta_path}")

    @classmethod
    def load(cls, index_path: str, meta_path: str) -> "VectorStore":
        """Carrega índice + metadados previamente salvos."""
        import faiss

        index = faiss.read_index(str(index_path))
        df = pd.read_parquet(meta_path)
        metas = [json.loads(m) for m in df["meta_json"].tolist()]
        textos = df["texto"].astype(str).tolist()
        return cls(index=index, metas=metas, textos=textos)

    @staticmethod
    def exists(index_path: str, meta_path: str) -> bool:
        """True se ambos os arquivos do índice existem em disco."""
        return Path(index_path).is_file() and Path(meta_path).is_file()

    # ---- busca ----
    def search(self, vetor_query: np.ndarray, k: int = 5) -> list[tuple[float, dict, str]]:
        """Retorna os top-k como `(score, meta, texto)`, ordenados por score desc."""
        if self.index is None:
            raise ValueError("Índice não carregado.")

        q = np.asarray(vetor_query, dtype=np.float32).reshape(1, -1)
        k = max(1, min(k, len(self.textos)))
        scores, idxs = self.index.search(q, k)

        resultados: list[tuple[float, dict, str]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:  # FAISS usa -1 para posições ausentes
                continue
            resultados.append((float(score), self.metas[idx], self.textos[idx]))
        return resultados
