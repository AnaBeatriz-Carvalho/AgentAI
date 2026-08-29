"""Subpacote RAG: busca semântica + citação de fonte sobre os discursos do Senado.

Pipelines independentes:
  - Indexação: DataFrame de discursos -> texto integral -> chunker -> embedder -> vectorstore (FAISS).
  - Query: pergunta -> embedder -> vectorstore (top-k) -> retriever -> LLM local -> resposta com fontes.

Mantém a filosofia do projeto (local, gratuito, PT-BR) e reaproveita a camada de citação/trace
já existente em src/ai/local_llm_handler.py.
"""
