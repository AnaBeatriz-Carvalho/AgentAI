import json
from types import SimpleNamespace
from datetime import date

import pandas as pd

import src.data.votacoes_handler as vh


class DummyResp:
    def __init__(self, payload):
        self._payload = payload

    @property
    def content(self):
        return json.dumps(self._payload).encode("utf-8")

    def raise_for_status(self):
        return None


def test_obter_votacoes_periodo_parsing(monkeypatch, tmp_path):
    # Evita escrever/ler cache real durante o teste.
    monkeypatch.setattr(vh, "CACHE_PATH", tmp_path / "cache.json")

    orientacao_payload = {
        "votacoes": [
            {
                "siglaTipoMateria": "PL",
                "numeroMateria": 1,
                "anoMateria": 2025,
                "descricaoVotacao": "Aprova o texto do projeto",
                "descricaoMateria": "Projeto de Lei n 1, de 2025",
                "dataInicioVotacao": "2025-10-01T10:00:00",
                "qtdVotosSim": 40,
                "qtdVotosNao": 5,
                "qtdVotosAbstencao": 0,
                "votosParlamentar": [
                    {"nomeParlamentar": "Fulano", "partido": "ABC", "uf": "SP", "voto": "SIM"},
                ],
            }
        ]
    }

    processo_payload = [
        {
            "codigoMateria": 999,
            "id": 123,
            "identificacao": "PL 1/2025",
            "ementa": "Ementa exemplo",
            "autoria": "Senador Fulano",
            "tipoDocumento": "Projeto de Lei",
            "situacaoAtual": "APROVADA NO PLENARIO",
            "urlDocumento": "http://exemplo/doc",
        }
    ]

    def fake_get(url, headers=None, timeout=None):
        if "orientacaoBancada" in url:
            return DummyResp(orientacao_payload)
        return DummyResp(processo_payload)

    monkeypatch.setattr(vh, "requests", SimpleNamespace(get=fake_get, RequestException=Exception))

    res = vh.obter_votacoes_periodo(date(2025, 10, 1), date(2025, 10, 2))

    assert isinstance(res, dict)
    assert len(res) == 1
    key = list(res.keys())[0]
    item = res[key]

    # Votos individuais parseados
    assert isinstance(item["df_votos"], pd.DataFrame)
    assert "Parlamentar" in item["df_votos"].columns
    assert item["df_votos"].iloc[0]["Parlamentar"] == "Fulano"

    # Enriquecimento via /processo presente nos detalhes
    detalhes = item["detalhes"]
    assert detalhes["ementa"] == "Ementa exemplo"
    assert detalhes["autores"] == "Senador Fulano"
    assert detalhes["tipo_documento"] == "Projeto de Lei"
    assert detalhes["descricao_votacao"] == "Aprova o texto do projeto"
    # Resultado derivado do placar
    assert detalhes["resultado"].startswith("Aprovada")
