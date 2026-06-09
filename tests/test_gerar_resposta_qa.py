"""Testes para a geração headless de QA (gerar_resposta_qa) e o construtor de prompt."""

from types import SimpleNamespace

import pandas as pd
import pytest

from src.ai import local_llm_handler as llm


def _df():
    return pd.DataFrame({
        "id_discurso": ["522046", "522043", "522041"],
        "Data": pd.to_datetime(["2025-05-05", "2025-05-06", "2025-05-07"]),
        "Parlamentar": ["Ana", "Bruno", "Carla"],
        "Partido": ["P1", "P2", "P3"],
        "Tema": ["Saúde", "Economia", "Educação"],
        "Resumo": [
            "Discurso sobre hospitais e vacinação",
            "Debate sobre impostos e mercado",
            "Investimento em escolas e universidades",
        ],
    })


def test_montar_prompt_qa_gera_refs_e_codigos():
    prompt, fontes, ids, codigos = llm._montar_prompt_qa(_df(), "fale sobre hospitais")
    assert "fale sobre hospitais" in prompt
    # Retrieval casa o discurso de saúde; ref citável é D1 e o código real é preservado.
    assert ids == ["D1"]
    assert codigos == ["522046"]
    assert fontes.iloc[0]["ref"] == "D1"


def _chunks(textos, modelo="mistral-test", tokens=None):
    for t in textos:
        yield SimpleNamespace(
            model=modelo,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=t))],
            usage=None,
        )
    if tokens is not None:
        # chunk final com usage e sem choices (padrão do include_usage).
        yield SimpleNamespace(model=modelo, choices=[], usage=SimpleNamespace(completion_tokens=tokens))


def test_gerar_resposta_qa_streaming(monkeypatch):
    def fake_create(**kwargs):
        assert kwargs.get("stream") is True
        assert kwargs.get("temperature") == 0.1
        assert kwargs.get("seed") == 42
        return _chunks(["Conforme ", "[D1]", "."], modelo="mistral-test", tokens=12)

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    timer = SimpleNamespace(_marked=False)
    timer.mark_first_token = lambda: setattr(timer, "_marked", True)

    res = llm.gerar_resposta_qa(_df(), "fale sobre hospitais",
                                temperature=0.1, seed=42, timer=timer, stream=True)
    assert res.resposta == "Conforme [D1]."
    assert res.modelo == "mistral-test"
    assert res.tokens_gerados == 12
    assert res.ids_recuperados == ["D1"]
    assert res.fontes_codigos == ["522046"]
    assert timer._marked is True  # primeiro token marcou a latência


def test_gerar_resposta_qa_sem_stream(monkeypatch):
    def fake_create(**kwargs):
        assert "stream" not in kwargs
        return SimpleNamespace(
            model="mistral-ns",
            choices=[SimpleNamespace(message=SimpleNamespace(content="Resposta [D1]."))],
            usage=SimpleNamespace(completion_tokens=5),
        )

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    res = llm.gerar_resposta_qa(_df(), "fale sobre hospitais", stream=False)
    assert res.resposta == "Resposta [D1]."
    assert res.modelo == "mistral-ns"
    assert res.tokens_gerados == 5


def test_gerar_resposta_qa_sem_seed_nao_envia_seed(monkeypatch):
    capturado = {}

    def fake_create(**kwargs):
        capturado.update(kwargs)
        return _chunks(["ok"], tokens=1)

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)
    llm.gerar_resposta_qa(_df(), "qualquer", seed=None, stream=True)
    assert "seed" not in capturado
