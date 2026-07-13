"""Testes da orquestração RAG (rag_chat) com retriever e LLM mockados.

Cobrem as duas rotas essenciais: sem contexto -> "não encontrei" (sem chamar o LLM);
com contexto -> resposta com >=1 fonte citada."""

from src.rag import rag_chat


class _FakeMessage:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _FakeCompletions:
    def __init__(self, texto):
        self.texto = texto
        self.chamou = False

    def create(self, **kwargs):
        self.chamou = True
        return type("R", (), {"choices": [_FakeMessage(self.texto)]})


def test_sem_fontes_retorna_nao_encontrei_sem_chamar_llm(monkeypatch):
    monkeypatch.setattr(rag_chat.retriever, "recuperar", lambda pergunta, k: ("", []))

    fake = _FakeCompletions("não deveria ser chamado")
    monkeypatch.setattr(rag_chat.local_llm_handler.client, "chat",
                        type("C", (), {"completions": fake}))

    out = rag_chat.responder("assunto inexistente", k=5)
    assert out["fontes"] == []
    assert "não encontrei" in out["resposta"].lower()
    assert fake.chamou is False


def test_com_fontes_gera_resposta_e_registra_trace(monkeypatch):
    fontes = [{
        "ref": "D1", "id_discurso": "111", "Data": "2025-03-12",
        "Parlamentar": "Fulano", "Partido": "ABC", "UF": "SP", "Tema": "Economia",
        "score": 0.91, "trecho": "falei sobre reforma tributária",
    }]
    monkeypatch.setattr(rag_chat.retriever, "recuperar",
                        lambda pergunta, k: ("[D1] Fulano (ABC), 2025-03-12: \"...\"", fontes))

    fake = _FakeCompletions("A reforma tributária foi discutida [D1].")
    monkeypatch.setattr(rag_chat.local_llm_handler.client, "chat",
                        type("C", (), {"completions": fake}))

    traces = []
    monkeypatch.setattr(rag_chat.local_llm_handler, "_registrar_trace",
                        lambda *a, **k: traces.append((a, k)))

    out = rag_chat.responder("o que falaram sobre reforma tributária?", k=3)
    assert fake.chamou is True
    assert out["fontes"] == fontes
    assert "[D1]" in out["resposta"]
    # trace registrado com origem própria do RAG
    assert traces and traces[0][1].get("origem") == "discurso_rag"
