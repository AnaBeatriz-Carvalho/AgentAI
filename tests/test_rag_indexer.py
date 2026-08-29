"""Testes do indexador: fallback para Resumo, contagem e persistência do índice.

Rede (texto integral) e embeddings são mockados; o FAISS real é usado para build/save/load."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("faiss")

from src.rag import indexer
from src.rag.vectorstore import VectorStore


def _fake_embed(textos, model_name=None):
    # vetores normalizados quaisquer, dimensão fixa, alinhados ao nº de chunks
    return (np.ones((len(textos), 4), dtype=np.float32) / 2.0)


def _df_discursos():
    return pd.DataFrame([
        {"id_discurso": "111", "Data": pd.Timestamp("2025-03-12"), "Parlamentar": "Fulano",
         "Partido": "ABC", "UF": "SP", "Resumo": "resumo curto A", "Tema": "Economia"},
        {"id_discurso": "222", "Data": pd.Timestamp("2025-03-13"), "Parlamentar": "Beltrana",
         "Partido": "XYZ", "UF": "RJ", "Resumo": "resumo curto B", "Tema": "Saúde"},
    ])


def test_fallback_para_resumo_quando_integral_vazio(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "buscar_texto_integral", lambda codigo: "")
    monkeypatch.setattr(indexer.embedder, "embed", _fake_embed)

    idx = tmp_path / "idx.faiss"
    meta = tmp_path / "meta.parquet"
    stats = indexer.indexar_discursos(_df_discursos(), str(idx), str(meta))

    assert stats["discursos"] == 2
    assert stats["com_integral"] == 0
    assert stats["com_fallback"] == 2
    assert stats["chunks"] == 2  # textos curtos -> 1 chunk cada

    vs = VectorStore.load(str(idx), str(meta))
    assert all(m["origem_texto"] == "resumo" for m in vs.metas)
    assert "resumo curto A" in vs.textos


def test_usa_texto_integral_quando_disponivel(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer, "buscar_texto_integral",
                        lambda codigo: f"texto integral longo do discurso {codigo} " * 3)
    monkeypatch.setattr(indexer.embedder, "embed", _fake_embed)

    idx = tmp_path / "idx.faiss"
    meta = tmp_path / "meta.parquet"
    stats = indexer.indexar_discursos(_df_discursos(), str(idx), str(meta))

    assert stats["com_integral"] == 2
    assert stats["com_fallback"] == 0
    vs = VectorStore.load(str(idx), str(meta))
    assert all(m["origem_texto"] == "integral" for m in vs.metas)
    assert vs.metas[0]["Data"] == "2025-03-12"  # Timestamp serializado


def test_df_vazio_nao_cria_indice(monkeypatch, tmp_path):
    monkeypatch.setattr(indexer.embedder, "embed", _fake_embed)
    idx = tmp_path / "idx.faiss"
    meta = tmp_path / "meta.parquet"
    stats = indexer.indexar_discursos(pd.DataFrame(), str(idx), str(meta))
    assert stats["chunks"] == 0
    assert not idx.exists()
