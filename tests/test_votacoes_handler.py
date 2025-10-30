from types import SimpleNamespace
from datetime import date
import pandas as pd

import src.data.votacoes_handler as vh


class DummyResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_obter_votacoes_periodo_parsing(monkeypatch):
    # minimal detalhes XML
    detalhes_xml = '''<Root>
      <Votacao>
        <siglaTipoMateria>PL</siglaTipoMateria>
        <numeroMateria>1</numeroMateria>
        <anoMateria>2025</anoMateria>
        <ementaMateria>Ementa exemplo</ementaMateria>
        <resultado>APROVADO</resultado>
        <descricaoVotacao>Nominal</descricaoVotacao>
      </Votacao>
    </Root>'''

    # minimal orientacoes XML
    orientacoes_xml = '''<Root>
      <votacoes>
        <descricaoMateria>PL 1/2025</descricaoMateria>
        <dataInicioVotacao>2025-10-01 10:00:00</dataInicioVotacao>
        <votosParlamentar>
          <nomeParlamentar>Fulano</nomeParlamentar>
          <partido>ABC</partido>
          <uf>SP</uf>
          <voto>SIM</voto>
        </votosParlamentar>
      </votacoes>
    </Root>'''

    def fake_get(url, headers=None, timeout=None):
        if 'orientacaoBancada' in url:
            return DummyResp(orientacoes_xml)
        return DummyResp(detalhes_xml)

    monkeypatch.setattr(vh, 'requests', SimpleNamespace(get=fake_get))

    res = vh.obter_votacoes_periodo(date(2025, 10, 1), date(2025, 10, 2))

    assert isinstance(res, dict)
    assert len(res) >= 1
    key = list(res.keys())[0]
    assert isinstance(res[key]['df_votos'], pd.DataFrame)
    assert 'Parlamentar' in res[key]['df_votos'].columns
