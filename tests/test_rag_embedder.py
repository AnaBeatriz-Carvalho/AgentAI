"""Testes do embedder com o modelo mockado (sem baixar PyTorch/pesos).

Validam o contrato do módulo: cache de modelo, formato (n, dim) float32, caso vazio e o
atalho embed_query. A qualidade semântica do modelo real não é testada aqui.
"""

import numpy as np

from src.rag import embedder


class _FakeModel:
    """Modelo falso: devolve vetores determinísticos e normalizados."""
    def __init__(self):
        self.chamadas = 0

    def encode(self, textos, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False):
        self.chamadas += 1
        base = np.array([[float(len(t)), 1.0, 2.0] for t in textos], dtype=np.float32)
        if normalize_embeddings:
            base = base / np.clip(np.linalg.norm(base, axis=1, keepdims=True), 1e-12, None)
        return base


def test_embed_vazio_retorna_array_vazio(monkeypatch):
    monkeypatch.setattr(embedder, "_load_model", lambda name: _FakeModel())
    out = embedder.embed([])
    assert out.shape == (0, 0)


def test_embed_formato_e_normalizacao(monkeypatch):
    monkeypatch.setattr(embedder, "_load_model", lambda name: _FakeModel())
    out = embedder.embed(["educação", "saúde pública"], model_name="fake")
    assert out.shape == (2, 3)
    assert out.dtype == np.float32
    normas = np.linalg.norm(out, axis=1)
    np.testing.assert_allclose(normas, [1.0, 1.0], atol=1e-5)


def test_embed_query_retorna_vetor_1d(monkeypatch):
    monkeypatch.setattr(embedder, "_load_model", lambda name: _FakeModel())
    v = embedder.embed_query("reforma tributária", model_name="fake")
    assert v.ndim == 1
    assert v.shape == (3,)
