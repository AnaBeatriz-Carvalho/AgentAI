"""Testes para o módulo local_llm_handler."""

import json
from types import SimpleNamespace
import pytest
from src.ai import local_llm_handler as llm


class MockChatResponse:
    """Mock para resposta de chat completion."""
    def __init__(self, content: str):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


class TestExtractFirstJsonObject:
    """Testes para _extract_first_json_object."""

    def test_extract_valid_json(self):
        """Deve extrair JSON válido."""
        text = 'Some text ```json {"key": "value"} ``` more text'
        result = llm._extract_first_json_object(text)
        assert result == '{"key": "value"}'

    def test_extract_json_without_markdown(self):
        """Deve extrair JSON sem markdown."""
        text = 'Text {"chave": "valor"} fim'
        result = llm._extract_first_json_object(text)
        assert result == '{"chave": "valor"}'

    def test_extract_no_json(self):
        """Deve retornar string vazia se não houver JSON."""
        text = "Apenas texto sem JSON"
        result = llm._extract_first_json_object(text)
        assert result == ""

    def test_extract_empty_string(self):
        """Deve retornar string vazia para entrada vazia."""
        result = llm._extract_first_json_object("")
        assert result == ""


class TestDefaultInsuficiente:
    """Testes para _default_insuficiente."""

    def test_default_structure(self):
        """Deve retornar dict com estrutura padrão."""
        result = llm._default_insuficiente()
        assert isinstance(result, dict)
        assert "parlamentar" in result
        assert "partido" in result
        assert "tema_principal" in result
        assert result["parlamentar"] == "não identificado"
        assert result["atores_mencionados"] == []


class TestCoerceAnalisePayload:
    """Testes para _coerce_analise_payload."""

    def test_valid_payload(self):
        """Deve processar payload válido."""
        payload = {
            "parlamentar": "João Silva",
            "partido": "ABC",
            "estado": "SP",
            "agenda_politica": "educação",
            "tema_principal": "educação superior",
            "resumo": "Discurso sobre educação",
            "posicionamento_governo": "apoio ao governo",
            "tom_politico": "crítico",
            "atores_mencionados": ["Ministro", "Senador"]
        }
        result = llm._coerce_analise_payload(payload)
        assert result["parlamentar"] == "João Silva"
        assert result["partido"] == "ABC"
        assert len(result["atores_mencionados"]) == 2

    def test_insufficient_content(self):
        """Deve retornar default para 'conteúdo insuficiente'."""
        payload = {"resumo": "conteúdo insuficiente"}
        result = llm._coerce_analise_payload(payload)
        assert result["resumo"] == "conteúdo insuficiente"
        assert result["parlamentar"] == "não identificado"

    def test_invalid_payload_type(self):
        """Deve retornar default para payload inválido."""
        result = llm._coerce_analise_payload("não é dict")
        assert isinstance(result, dict)
        assert result["parlamentar"] == "não identificado"

    def test_normalize_atores_mencionados(self):
        """Deve normalizar lista de atores."""
        payload = {
            "atores_mencionados": ["  Ator 1  ", "Ator 2", None, "", "  Ator 3  "]
        }
        result = llm._coerce_analise_payload(payload)
        assert result["atores_mencionados"] == ["Ator 1", "Ator 2", "Ator 3"]

    def test_max_cinco_atores(self):
        """Deve limitar a 5 atores mencionados."""
        payload = {
            "atores_mencionados": ["A", "B", "C", "D", "E", "F", "G"]
        }
        result = llm._coerce_analise_payload(payload)
        assert len(result["atores_mencionados"]) == 5


class TestAnalisarDiscursoStruct:
    """Testes para analisar_discurso_struct."""

    def test_texto_muito_curto(self):
        """Deve retornar default para texto muito curto."""
        result = llm.analisar_discurso_struct("abc")
        assert result["parlamentar"] == "não identificado"

    def test_texto_vazio(self):
        """Deve retornar default para texto vazio."""
        result = llm.analisar_discurso_struct("")
        assert result["parlamentar"] == "não identificado"

    def test_analisar_com_mock(self, monkeypatch):
        """Deve analisar discurso quando API responde corretamente."""
        response_content = json.dumps({
            "parlamentar": "João Silva",
            "partido": "PT",
            "estado": "SP",
            "agenda_politica": "educação",
            "tema_principal": "educação",
            "resumo": "Discussão sobre educação",
            "posicionamento_governo": "apoio ao governo",
            "tom_politico": "crítico",
            "atores_mencionados": ["Ministro"]
        })

        def mock_create(*args, **kwargs):
            return MockChatResponse(response_content)

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        texto = "A" * 50  # Texto com mais de 40 chars
        result = llm.analisar_discurso_struct(texto)
        assert result["parlamentar"] == "João Silva"
        assert result["partido"] == "PT"

    def test_analisar_com_resposta_invalida(self, monkeypatch):
        """Deve retornar default quando API retorna JSON inválido."""
        def mock_create(*args, **kwargs):
            return MockChatResponse("não é JSON válido")

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        texto = "A" * 50
        result = llm.analisar_discurso_struct(texto)
        assert result["parlamentar"] == "não identificado"

    def test_analisar_com_erro_api(self, monkeypatch):
        """Deve retornar default quando API lança exceção."""
        def mock_create(*args, **kwargs):
            raise Exception("Erro na API")

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        texto = "A" * 50
        result = llm.analisar_discurso_struct(texto)
        assert result["parlamentar"] == "não identificado"


class TestClassificarTemaLocal:
    """Testes para classificar_tema_local."""

    def test_classificar_tema_valido(self, monkeypatch):
        """Deve classificar tema corretamente."""
        response_content = json.dumps({"tema": "Educação"})

        def mock_create(*args, **kwargs):
            return MockChatResponse(response_content)

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        temas = ["Saúde", "Educação", "Economia"]
        resultado = llm.classificar_tema_local("Isso é sobre educação superior", temas)
        assert resultado == "Educação"

    def test_classificar_tema_fallback_direto(self, monkeypatch):
        """Deve fazer fallback para match direto quando JSON inválido."""
        def mock_create(*args, **kwargs):
            return MockChatResponse("Menção a Educação em texto")

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        temas = ["Saúde", "Educação", "Economia"]
        resultado = llm.classificar_tema_local("Sobre educação", temas)
        assert resultado == "Educação"

    def test_classificar_tema_outros_default(self, monkeypatch):
        """Deve retornar 'Outros' quando nenhum match."""
        def mock_create(*args, **kwargs):
            return MockChatResponse("Nenhum tema relevante")

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        temas = ["Saúde", "Educação", "Economia"]
        resultado = llm.classificar_tema_local("Texto genérico", temas)
        assert resultado == "Outros"

    def test_classificar_tema_com_erro(self, monkeypatch):
        """Deve retornar 'Outros' quando API lança erro."""
        def mock_create(*args, **kwargs):
            raise Exception("Erro na API")

        monkeypatch.setattr(llm.client.chat.completions, "create", mock_create)

        temas = ["Saúde", "Educação", "Economia"]
        resultado = llm.classificar_tema_local("Resumo", temas)
        assert resultado == "Outros"
