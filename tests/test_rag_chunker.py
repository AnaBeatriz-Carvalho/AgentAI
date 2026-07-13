"""Testes do chunker do RAG: tamanho, overlap, herança de metadados e casos de borda."""

import pytest

from src.rag.chunker import chunk_texto


def test_texto_vazio_retorna_lista_vazia():
    assert chunk_texto("", {"id_discurso": "D1"}) == []
    assert chunk_texto("   ", {"id_discurso": "D1"}) == []


def test_texto_curto_gera_um_unico_chunk():
    chunks = chunk_texto("reforma tributária no senado", {"id_discurso": "D1"}, chunk_size=400, overlap=64)
    assert len(chunks) == 1
    assert chunks[0]["texto"] == "reforma tributária no senado"


def test_metadados_sao_herdados_por_todos_os_chunks():
    meta = {"id_discurso": "D9", "Parlamentar": "Fulano", "Partido": "XYZ"}
    texto = " ".join(str(i) for i in range(50))
    chunks = chunk_texto(texto, meta, chunk_size=10, overlap=2)
    assert len(chunks) > 1
    for c in chunks:
        assert c["meta"] == meta
        # cópia defensiva: mutar o retorno não afeta o meta original
        c["meta"]["Partido"] = "MUDOU"
    assert meta["Partido"] == "XYZ"


def test_tamanho_e_overlap_respeitados():
    palavras = [f"w{i}" for i in range(25)]
    texto = " ".join(palavras)
    chunks = chunk_texto(texto, {}, chunk_size=10, overlap=3)

    # passo = 10 - 3 = 7 -> inícios em 0, 7, 14, 21
    assert len(chunks) == 4
    assert chunks[0]["texto"].split() == palavras[0:10]
    assert chunks[1]["texto"].split() == palavras[7:17]
    # overlap: fim do chunk 0 reaparece no começo do chunk 1
    assert palavras[7:10] == chunks[1]["texto"].split()[:3]
    # último chunk cobre o fim sem estourar
    assert chunks[-1]["texto"].split()[-1] == "w24"


def test_overlap_invalido_levanta_erro():
    with pytest.raises(ValueError):
        chunk_texto("a b c", {}, chunk_size=5, overlap=5)
    with pytest.raises(ValueError):
        chunk_texto("a b c", {}, chunk_size=0, overlap=0)
