"""Testes do vectorstore: round-trip build -> save -> load -> search.

Requer `faiss` instalado; caso contrário o módulo é ignorado (importorskip)."""

import numpy as np
import pytest

faiss = pytest.importorskip("faiss")

from src.rag.vectorstore import VectorStore


def _vetores_norm(matriz: np.ndarray) -> np.ndarray:
    """Normaliza L2 as linhas (o embedder real já faz isso; aqui replicamos p/ o teste)."""
    matriz = np.asarray(matriz, dtype=np.float32)
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    return matriz / np.clip(normas, 1e-12, None)


def test_build_search_recupera_vetor_mais_proximo():
    vetores = _vetores_norm(np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]))
    metas = [{"id_discurso": "D1"}, {"id_discurso": "D2"}, {"id_discurso": "D3"}]
    textos = ["educação", "saúde", "economia"]

    vs = VectorStore().build(vetores, metas, textos)
    resultados = vs.search(vetores[1], k=1)

    assert len(resultados) == 1
    score, meta, texto = resultados[0]
    assert meta["id_discurso"] == "D2"
    assert texto == "saúde"
    assert score == pytest.approx(1.0, abs=1e-5)


def test_round_trip_save_load(tmp_path):
    vetores = _vetores_norm(np.random.RandomState(0).randn(10, 8))
    metas = [{"id_discurso": f"D{i}", "Parlamentar": f"Sen {i}"} for i in range(10)]
    textos = [f"trecho {i}" for i in range(10)]

    index_path = tmp_path / "idx.faiss"
    meta_path = tmp_path / "meta.parquet"

    VectorStore().build(vetores, metas, textos).save(str(index_path), str(meta_path))
    assert VectorStore.exists(str(index_path), str(meta_path))

    vs = VectorStore.load(str(index_path), str(meta_path))
    assert len(vs.textos) == 10
    assert vs.metas[3]["id_discurso"] == "D3"

    # a busca pelo próprio vetor 5 deve trazê-lo no topo, preservando meta/texto
    top = vs.search(vetores[5], k=3)
    assert top[0][1]["id_discurso"] == "D5"
    assert top[0][2] == "trecho 5"


def test_search_k_maior_que_colecao_nao_quebra():
    vetores = _vetores_norm(np.eye(3, dtype=np.float32))
    vs = VectorStore().build(vetores, [{"i": 0}, {"i": 1}, {"i": 2}], ["a", "b", "c"])
    resultados = vs.search(vetores[0], k=99)
    assert len(resultados) == 3
