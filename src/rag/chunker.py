"""Quebra o texto de um discurso em trechos (chunks) com sobreposição.

Chunks com overlap evitam perder contexto nas bordas — um assunto que começa no fim de um
trecho e continua no próximo permanece recuperável em ambos. O tamanho é medido em palavras
(aproximação simples e determinística de tokens, sem dependência de tokenizer externo).
"""

from typing import Optional


def chunk_texto(
    texto: str,
    meta: Optional[dict] = None,
    chunk_size: int = 400,
    overlap: int = 64,
) -> list[dict]:
    """Fatia `texto` em trechos de ~`chunk_size` palavras com `overlap` de sobreposição.

    Cada item devolvido é ``{"texto": <trecho>, "meta": <cópia dos metadados>}``. Os
    metadados (senador, data, id do discurso...) são herdados por todos os chunks do mesmo
    discurso — é o que permite a citação da fonte depois.

    - Texto vazio/só espaços -> lista vazia.
    - Texto curto (ex.: um `Resumo`) -> um único chunk.
    """
    meta = dict(meta) if meta else {}

    palavras = (texto or "").split()
    if not palavras:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap deve estar em [0, chunk_size)")

    passo = chunk_size - overlap
    chunks: list[dict] = []
    for inicio in range(0, len(palavras), passo):
        trecho = " ".join(palavras[inicio:inicio + chunk_size])
        chunks.append({"texto": trecho, "meta": dict(meta)})
        if inicio + chunk_size >= len(palavras):
            break  # último trecho já cobriu o fim; evita chunk final redundante
    return chunks
