"""Recuperação densa (FAISS) sobre o corpus CONGELADO da avaliação de geração.

Usada só na Fase 2 da avaliação (comparação palavra-chave x denso). Indexa em memória
os 152 registros do `corpus_snapshot.csv` com o mesmo embedder do chat (`src/rag/embedder`,
modelo definido em `RAG_EMBEDDING_MODEL`) e devolve os k mais similares à pergunta, na
mesma forma de DataFrame que `_selecionar_fontes`. Assim, entre as duas condições muda
apenas o recuperador: corpus, perguntas, prompt, k e hiperparâmetros ficam fixos.

O índice não é persistido: é reconstruído a cada execução a partir do snapshot, para que
a condição seja reproduzível sem depender do índice do chat ao vivo (que cobre outro corpus).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.constants import MAX_FONTES_PROMPT
from src.rag import embedder

COLUNAS_TEXTO = ["Parlamentar", "Tema", "Resumo"]


def texto_indexado(linha: pd.Series) -> str:
    """Texto de cada registro no índice: autor, tema e resumo (o que o snapshot contém)."""
    partes = [str(linha.get(c, "") or "") for c in COLUNAS_TEXTO]
    return " | ".join(p for p in partes if p and p != "nan")


class RecuperadorDenso:
    def __init__(self, df: pd.DataFrame, model_name: str | None = None):
        self.df = df.reset_index(drop=True)
        self.model_name = model_name
        textos = [texto_indexado(r) for _, r in self.df.iterrows()]
        self.vetores = embedder.embed(textos, model_name=model_name)
        import faiss
        self.index = faiss.IndexFlatIP(self.vetores.shape[1])
        self.index.add(np.asarray(self.vetores, dtype=np.float32))

    def selecionar(self, pergunta: str, k: int = MAX_FONTES_PROMPT) -> pd.DataFrame:
        """Top-k registros por similaridade de cosseno, em ordem decrescente de score."""
        q = embedder.embed_query(pergunta, model_name=self.model_name).reshape(1, -1)
        k = max(1, min(k, len(self.df)))
        scores, idxs = self.index.search(np.asarray(q, dtype=np.float32), k)
        ordem = [i for i in idxs[0] if i >= 0]
        out = self.df.iloc[ordem].copy()
        out["score_denso"] = [float(s) for s, i in zip(scores[0], idxs[0]) if i >= 0]
        return out
