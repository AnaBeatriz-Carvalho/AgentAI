"""Testes para o módulo local_llm_handler."""

import json
from types import SimpleNamespace
import pandas as pd
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


class TestSelecionarFontes:
    """Testes para _selecionar_fontes (retrieval por palavra-chave)."""

    def _df(self):
        return pd.DataFrame({
            "id_discurso": ["D1", "D2", "D3"],
            "Parlamentar": ["Ana", "Bruno", "Carla"],
            "Tema": ["Saúde", "Economia", "Educação"],
            "Partido": ["P1", "P2", "P3"],
            "Resumo": [
                "Discurso sobre hospitais e vacinação",
                "Debate sobre impostos e mercado",
                "Investimento em escolas e universidades",
            ],
        })

    def test_df_vazio_retorna_vazio(self):
        vazio = pd.DataFrame()
        assert llm._selecionar_fontes(vazio, "qualquer").empty

    def test_casa_por_termo(self):
        out = llm._selecionar_fontes(self._df(), "o que disseram sobre hospitais?")
        assert out["id_discurso"].tolist() == ["D1"]

    def test_ignora_acento(self):
        # "saude" (sem acento) deve casar o tema "Saúde".
        out = llm._selecionar_fontes(self._df(), "fale sobre saude")
        assert "D1" in out["id_discurso"].tolist()

    def test_ranqueia_por_numero_de_matches(self):
        # Termos casam D3 (escolas + universidades) mais fortemente que outros.
        out = llm._selecionar_fontes(self._df(), "escolas e universidades")
        assert out.iloc[0]["id_discurso"] == "D3"

    def test_fallback_sem_correspondencia(self):
        df = self._df()
        out = llm._selecionar_fontes(df, "termo inexistente xyzzy")
        # Sem match, devolve a amostra geral (todas as linhas, até o limite).
        assert len(out) == len(df)

    def test_colunas_busca_customizadas(self):
        df = pd.DataFrame({
            "id_voto": ["V1", "V2"],
            "Parlamentar": ["Ana Silva", "Bruno Costa"],
            "Voto": ["Sim", "Não"],
        })
        out = llm._selecionar_fontes(df, "como votou a senadora Silva?", colunas_busca=["Parlamentar", "Voto"])
        assert out["id_voto"].tolist() == ["V1"]


class TestRegistrarTrace:
    """Testes para _registrar_trace (log JSONL de rastreabilidade)."""

    def test_grava_linha_com_campos_esperados(self, tmp_path, monkeypatch):
        trace_path = tmp_path / "qa_trace.jsonl"
        monkeypatch.setattr(llm, "_TRACE_PATH", trace_path)

        llm._registrar_trace("Pergunta?", ["D1", "D2"], "Resposta [D1].", origem="discurso")

        linhas = trace_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(linhas) == 1
        reg = json.loads(linhas[0])
        assert reg["origem"] == "discurso"
        assert reg["pergunta"] == "Pergunta?"
        assert reg["fontes_ids"] == ["D1", "D2"]
        assert reg["n_fontes"] == 2
        assert reg["resposta"] == "Resposta [D1]."

    def test_origem_votacao_e_ids_coercidos_para_str(self, tmp_path, monkeypatch):
        trace_path = tmp_path / "qa_trace.jsonl"
        monkeypatch.setattr(llm, "_TRACE_PATH", trace_path)

        llm._registrar_trace("P", [1, 2, 3], "R", origem="votacao")

        reg = json.loads(trace_path.read_text(encoding="utf-8").strip())
        assert reg["origem"] == "votacao"
        assert reg["fontes_ids"] == ["1", "2", "3"]
        # Sem fontes_codigos fornecido, o campo não deve aparecer.
        assert "fontes_codigos" not in reg

    def test_grava_fontes_codigos_quando_fornecido(self, tmp_path, monkeypatch):
        trace_path = tmp_path / "qa_trace.jsonl"
        monkeypatch.setattr(llm, "_TRACE_PATH", trace_path)

        llm._registrar_trace(
            "P", ["D1", "D2"], "Resposta [D1].", origem="discurso",
            fontes_codigos=["522046", "522043"],
        )

        reg = json.loads(trace_path.read_text(encoding="utf-8").strip())
        assert reg["fontes_ids"] == ["D1", "D2"]
        assert reg["fontes_codigos"] == ["522046", "522043"]
