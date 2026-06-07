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
    assert set(['id_discurso', 'Data', 'Parlamentar', 'Partido', 'UF', 'Resumo']).issubset(df.columns)


def test_id_discurso_sequencial_sem_codigo(monkeypatch):
    """Sem código na API, o id_discurso deve ser sequencial (D1, D2, ...)."""
    sample_xml = '''<ListaPronunciamentos>
    <Pronunciamento>
        <Data>2025-10-01</Data>
        <NomeAutor>Fulano</NomeAutor>
        <Partido>ABC</Partido>
        <UF>SP</UF>
        <Resumo>Primeiro pronunciamento</Resumo>
    </Pronunciamento>
    <Pronunciamento>
        <Data>2025-10-02</Data>
        <NomeAutor>Beltrano</NomeAutor>
        <Partido>XYZ</Partido>
        <UF>RJ</UF>
        <Resumo>Segundo pronunciamento</Resumo>
    </Pronunciamento>
</ListaPronunciamentos>'''

    monkeypatch.setattr(dp, "requests", SimpleNamespace(get=lambda *a, **k: DummyResp(sample_xml)))

    df = dp.extrair_discursos_senado(date(2025, 10, 1), date(2025, 10, 2))

    assert df['id_discurso'].tolist() == ['D1', 'D2']


def test_id_discurso_usa_codigo_pronunciamento(monkeypatch):
    """Quando a API traz CodigoPronunciamento, ele deve virar o id_discurso."""
    sample_xml = '''<ListaPronunciamentos>
    <Pronunciamento>
        <CodigoPronunciamento>998877</CodigoPronunciamento>
        <Data>2025-10-01</Data>
        <NomeAutor>Fulano</NomeAutor>
        <Partido>ABC</Partido>
        <UF>SP</UF>
        <Resumo>Pronunciamento com codigo</Resumo>
    </Pronunciamento>
</ListaPronunciamentos>'''

    monkeypatch.setattr(dp, "requests", SimpleNamespace(get=lambda *a, **k: DummyResp(sample_xml)))

    df = dp.extrair_discursos_senado(date(2025, 10, 1), date(2025, 10, 1))

    assert df['id_discurso'].tolist() == ['998877']


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
