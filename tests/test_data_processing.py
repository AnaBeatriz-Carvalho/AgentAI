from datetime import date

import pandas as pd

from types import SimpleNamespace

import src.data.data_processing as dp


class DummyResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_extrair_discursos_senado_parsing(monkeypatch):
    sample_xml = '''<ListaPronunciamentos>
    <Pronunciamento>
        <Data>2025-10-01</Data>
        <NomeAutor>Fulano de Tal</NomeAutor>
        <Partido>ABC</Partido>
        <UF>SP</UF>
        <Resumo>Texto do pronunciamento 1</Resumo>
    </Pronunciamento>
    <Pronunciamento>
        <Data>2025-10-02</Data>
        <NomeAutor>Beltrano</NomeAutor>
        <Partido>XYZ</Partido>
        <UF>RJ</UF>
        <Resumo>Texto do pronunciamento 2</Resumo>
    </Pronunciamento>
</ListaPronunciamentos>'''

    def fake_get(url, headers=None, timeout=None):
        return DummyResp(sample_xml)

    monkeypatch.setattr(dp, "requests", SimpleNamespace(get=fake_get))

    df = dp.extrair_discursos_senado(date(2025, 10, 1), date(2025, 10, 2))

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert set(['Data', 'Parlamentar', 'Partido', 'UF', 'Resumo']).issubset(df.columns)


def test_classificar_tema_discursos_com_local_llm(monkeypatch):
    df = pd.DataFrame({'Resumo': ['texto sobre saúde e hospitais']})

    # força classificação determinística sem chamar LLM
    monkeypatch.setattr(dp, 'classificar_tema_local', lambda resumo, temas: 'Saúde')

    # stub do progress bar do streamlit
    class P:
        def progress(self, *a, **k):
            return None

        def empty(self):
            return None

    monkeypatch.setattr(dp.st, 'progress', lambda *a, **k: P())

    out = dp.classificar_tema_discursos_com_local_llm(df.copy(), sleep_between_batches=0.0)

    assert 'Tema' in out.columns
    assert out.loc[0, 'Tema'] == 'Saúde'
