"""Testes do recuperador denso da avaliação (embedder substituído por um fake determinístico)."""
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("faiss")

from src.eval import recuperador_denso as rd

VOCAB = ["conab", "saude", "escola", "imposto"]


def _fake_embed(textos, model_name=None):
    m = np.array([[t.lower().count(w) + 0.01 for w in VOCAB] for t in textos], dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def _fake_query(p, model_name=None):
    return _fake_embed([p])[0]


def _df():
    return pd.DataFrame({
        "id_discurso": ["1", "2", "3"],
        "Parlamentar": ["Ana", "Bruno", "Carla"],
        "Tema": ["Economia", "Saúde", "Educação"],
        "Resumo": ["Aniversario da Conab conab", "Saude publica saude", "Escola e escola"],
    })


def test_ordena_por_similaridade(monkeypatch):
    monkeypatch.setattr(rd.embedder, "embed", _fake_embed)
    monkeypatch.setattr(rd.embedder, "embed_query", _fake_query)
    r = rd.RecuperadorDenso(_df())
    top = r.selecionar("quem falou da conab", k=2)
    assert list(top["id_discurso"])[0] == "1"
    assert len(top) == 2 and top["score_denso"].is_monotonic_decreasing


def test_k_limitado_ao_corpus(monkeypatch):
    monkeypatch.setattr(rd.embedder, "embed", _fake_embed)
    monkeypatch.setattr(rd.embedder, "embed_query", _fake_query)
    assert len(rd.RecuperadorDenso(_df()).selecionar("x", k=99)) == 3
