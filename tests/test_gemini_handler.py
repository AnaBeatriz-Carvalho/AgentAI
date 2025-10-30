from types import SimpleNamespace
import pandas as pd

import src.ai.gemini_handler as gh


def test_responder_pergunta_usuario_appends_message(monkeypatch):
    # prepare a tiny dataframe
    df = pd.DataFrame({'Resumo': ['teste']})

    # fake genai model
    class FakeModel:
        def __init__(self, *a, **k):
            pass

        def generate_content(self, prompt):
            return SimpleNamespace(text='Resposta do agente')

    monkeypatch.setattr(gh, 'genai', SimpleNamespace(GenerativeModel=FakeModel))

    # stub streamlit session_state and chat functions used by the handler
    class FakeSession(dict):
        def __init__(self):
            super().__init__()
            self.messages = []

        def __contains__(self, key):
            return dict.__contains__(self, key) or hasattr(self, key)

        def __setitem__(self, key, value):
            dict.__setitem__(self, key, value)
            setattr(self, key, value)

    fake_state = FakeSession()
    monkeypatch.setattr(gh.st, 'session_state', fake_state)

    class ChatMsg:
        def __init__(self, role):
            self.role = role

        def write(self, *a, **k):
            return None

    monkeypatch.setattr(gh.st, 'chat_message', lambda role: ChatMsg(role))

    class Spinner:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(gh.st, 'spinner', lambda *a, **k: Spinner())

    gh.responder_pergunta_usuario(df, 'Qual o tema?')

    # after calling, session_state.messages must contain two entries (user + assistant)
    assert isinstance(gh.st.session_state.messages, list)
    assert any(m.get('role') == 'assistant' for m in gh.st.session_state.messages)
