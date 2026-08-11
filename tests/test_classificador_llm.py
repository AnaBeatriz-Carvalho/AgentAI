"""Testes do classificador LLM few-shot (sem depender do LM Studio: client fake)."""

import pytest

from src.eval import classificador_llm as clf
from src.eval.categorias import CATEGORIAS, CAT_OUTROS


class _FakeMessage:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeMessage(content)]


class _FakeClient:
    """Simula client.chat.completions.create devolvendo um conteúdo fixo."""

    def __init__(self, content):
        self._content = content
        self.chamadas = []
        self.chat = type("C", (), {"completions": self})()

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        return _FakeResp(self._content)


def test_mapeia_categoria_exata():
    client = _FakeClient("Saúde")
    assert clf.classificar_llm("qualquer resumo", modelo="fake", client=client) == "Saúde"


def test_mapeia_resposta_com_ruido():
    # Modelo devolve frase com pontuação/prefixo — deve casar por substring.
    client = _FakeClient("Categoria: Meio Ambiente.")
    assert clf.classificar_llm("resumo", modelo="fake", client=client) == "Meio Ambiente"


def test_mapeia_sem_acento():
    client = _FakeClient("politica/institucional")
    assert clf.classificar_llm("resumo", modelo="fake", client=client) == "Política/Institucional"


def test_resposta_invalida_vira_outros():
    client = _FakeClient("Esportes Radicais")
    assert clf.classificar_llm("resumo", modelo="fake", client=client) == CAT_OUTROS


def test_resumo_vazio_nao_chama_modelo():
    client = _FakeClient("Saúde")
    assert clf.classificar_llm("   ", modelo="fake", client=client) == CAT_OUTROS
    assert client.chamadas == []  # não deve ter chamado a API


def test_erro_de_api_vira_outros():
    class _Boom:
        def __init__(self):
            self.chat = type("C", (), {"completions": self})()

        def create(self, **kwargs):
            raise RuntimeError("sem servidor")

    assert clf.classificar_llm("resumo", modelo="fake", client=_Boom()) == CAT_OUTROS


def test_todas_categorias_sao_mapeaveis():
    # Garante que cada rótulo canônico retorna a si mesmo (sem cair em Outros por engano).
    for cat in CATEGORIAS:
        client = _FakeClient(cat)
        assert clf.classificar_llm("resumo", modelo="fake", client=client) == cat


def test_prompt_contem_categorias_e_exemplos():
    p = clf.construir_prompt("um resumo de teste")
    for cat in CATEGORIAS:
        assert cat in p
    assert "um resumo de teste" in p
    assert "Exemplos:" in p
