"""Testes do conector SAPL e do QA municipal, com a API simulada.

Os payloads imitam respostas reais do SAPL 3.x (Câmara de Lagarto/SE, out/2026),
reduzidos ao necessário.
"""

import json
from datetime import date
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest
import requests

from src.ai import municipal_qa
from src.sapl import normalizacao as nz
from src.sapl.camaras import normalizar_url_base
from src.sapl.client import SaplClient, SaplErro
from src.sapl.servico import carregar_camara
from src.utils.rastreabilidade import extrair_ids_citados

BASE = "https://sapl.exemplo.se.leg.br"


def _pagina(results, page=1, next_page=None):
    return {
        "pagination": {"next_page": next_page, "page": page, "total_entries": len(results)},
        "results": results,
    }


MATERIAS = [
    {"id": 7050, "numero": 1, "ano": 2026, "tipo": 8, "data_apresentacao": "2026-02-19",
     "ementa": "Reforma da Praça Santa Luzia e pavimentação da rua", "autores": [56],
     "em_tramitacao": False, "texto_original": f"{BASE}/media/ind_01-2026.pdf"},
    {"id": 7051, "numero": 2, "ano": 2026, "tipo": 8, "data_apresentacao": "2026-02-20",
     "ementa": "Reabertura do posto de saúde do povoado", "autores": [56, 99],
     "em_tramitacao": True, "texto_original": None},
]
TIPOS = [{"id": 8, "sigla": "IND", "descricao": "Indicação"}]
AUTORES = [
    {"id": 56, "nome": "Acácia Ribeiro", "object_id": 40, "tipo": 1},
    # Autor não-parlamentar cujo object_id colide numericamente com um vereador.
    {"id": 99, "nome": "Poder Executivo", "object_id": 41, "tipo": 3},
]
PARLAMENTARES = [
    {"id": 40, "nome_parlamentar": "Acácia Ribeiro", "nome_completo": "Maria Acácia Carvalho Ribeiro",
     "ativo": True, "profissao": "Assistente Social", "email": "acacia@lagarto.se.leg.br",
     "telefone": "(79) 99999-0000", "fotografia": f"{BASE}/media/40.jpg"},
    {"id": 41, "nome_parlamentar": "Fulano", "nome_completo": "Fulano de Tal", "ativo": False,
     "profissao": "", "email": "fulano@hotmail.com", "fotografia": ""},
]
PARTIDOS = [{"id": 31, "sigla": "PSD"}, {"id": 9, "sigla": "PTC"}]
FILIACOES = [
    {"parlamentar": 40, "partido": 9, "data": "2010-01-01", "data_desfiliacao": "2015-01-01"},
    {"parlamentar": 40, "partido": 31, "data": "2015-02-01", "data_desfiliacao": None},
]
VOTACOES = [
    {"id": 1, "materia": 7051, "data_hora": "2026-02-25T16:28:02-03:00",
     "numero_votos_sim": 15, "numero_votos_nao": 0, "numero_abstencoes": 1, "observacao": "",
     "__str__": "Ordem: Ordem do Dia/Expediente: 1 - Indicação nº 2 de 2026 em 6ª Ordinária - Votação: Aprovado"},
    {"id": 2, "materia": 380, "data_hora": "2019-05-15T16:28:02-03:00",
     "numero_votos_sim": 17, "numero_votos_nao": 0, "numero_abstencoes": 0, "observacao": "",
     "__str__": "Ordem: Ordem do Dia/Expediente: 1 - PLC nº 1 de 2017 em 6ª Ordinária - Votação: Aprovado"},
]


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    @property
    def content(self):
        return json.dumps(self._payload).encode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    """Responde por endpoint; ``paginas`` permite simular paginação."""

    def __init__(self, rotas: dict, falhar: set | None = None):
        self.rotas, self.falhar, self.chamadas = rotas, falhar or set(), []

    def get(self, url, params=None, headers=None, timeout=None):
        caminho = urlparse(url).path.split("/api/", 1)[1]
        self.chamadas.append((caminho, dict(params or {})))
        if caminho in self.falhar:
            return FakeResp({}, status=500)
        rota = self.rotas.get(caminho, [])
        pagina = int((params or {}).get("page", 1))
        if rota and isinstance(rota[0], list):  # lista de páginas
            itens = rota[pagina - 1]
            proxima = pagina + 1 if pagina < len(rota) else None
            return FakeResp(_pagina(itens, pagina, proxima))
        return FakeResp(_pagina(rota))


def _rotas_padrao():
    return {
        "materia/materialegislativa/": MATERIAS,
        "materia/tipomaterialegislativa/": TIPOS,
        "base/autor/": AUTORES,
        "parlamentares/parlamentar/": PARLAMENTARES,
        "parlamentares/filiacao/": FILIACOES,
        "parlamentares/partido/": PARTIDOS,
        "sessao/registrovotacao/": VOTACOES,
    }


# --- URL ---------------------------------------------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    ("sapl.lagarto.se.leg.br", "https://sapl.lagarto.se.leg.br"),
    ("https://sapl.lagarto.se.leg.br/", "https://sapl.lagarto.se.leg.br"),
    ("https://sapl.lagarto.se.leg.br/api/", "https://sapl.lagarto.se.leg.br"),
])
def test_normalizar_url_base(entrada, esperado):
    assert normalizar_url_base(entrada) == esperado


@pytest.mark.parametrize("entrada", ["", "   ", "ftp://x.y", "localhost"])
def test_normalizar_url_base_invalida(entrada):
    with pytest.raises(ValueError):
        normalizar_url_base(entrada)


# --- Cliente -------------------------------------------------------------------------

def test_cliente_percorre_paginas_e_envia_filtros():
    sess = FakeSession({"materia/materialegislativa/": [[MATERIAS[0]], [MATERIAS[1]]]})
    cli = SaplClient(BASE, session=sess, pausa=0)
    itens = cli.materias("2026-01-01", "2026-03-01")
    assert [m["id"] for m in itens] == [7050, 7051]
    assert [p["page"] for _, p in sess.chamadas] == [1, 2]
    assert sess.chamadas[0][1]["data_apresentacao__gte"] == "2026-01-01"
    assert sess.chamadas[0][1]["o"] == "-data_apresentacao"


def test_cliente_respeita_max_paginas():
    sess = FakeSession({"base/autor/": [[a] for a in AUTORES * 5]})
    cli = SaplClient(BASE, session=sess, pausa=0)
    assert len(cli.listar_tudo("base/autor/", max_paginas=3)) == 3


def test_cliente_erro_http_vira_sapl_erro():
    cli = SaplClient(BASE, session=FakeSession({}, falhar={"base/autor/"}), pausa=0)
    with pytest.raises(SaplErro):
        cli.autores()


# --- Normalização --------------------------------------------------------------------

def test_partido_atual_usa_filiacao_vigente():
    assert nz.partido_atual_por_parlamentar(FILIACOES, nz.mapa_partidos(PARTIDOS)) == {40: "PSD"}


def test_partido_fallback_pelo_rotulo_da_filiacao():
    fil = [{"parlamentar": 7, "partido": 123, "data": "2020-01-01", "data_desfiliacao": None,
            "__str__": "Beltrano - MDB - Movimento Democrático Brasileiro"}]
    assert nz.partido_atual_por_parlamentar(fil, {}) == {7: "MDB"}


def test_autor_nao_parlamentar_nao_herda_partido_por_colisao_de_id():
    autores = nz.mapa_autores(AUTORES, PARLAMENTARES)
    assert autores[56]["parlamentar_id"] == 40
    assert autores[99]["parlamentar_id"] is None  # object_id 41 existe, mas o nome não confere


def test_normalizar_materias_resolve_tipo_autor_partido_link():
    df = nz.normalizar_materias(
        MATERIAS, nz.mapa_tipos(TIPOS), nz.mapa_autores(AUTORES, PARLAMENTARES), {40: "PSD"}, BASE
    )
    linha = df[df["id_materia"] == 7051].iloc[0]
    assert linha["Identificação"] == "IND 2/2026"
    assert linha["Tipo"] == "Indicação"
    assert linha["Autores"] == "Acácia Ribeiro, Poder Executivo"
    assert linha["Partido"] == "PSD"
    assert linha["Link"] == f"{BASE}/materia/7051"
    assert linha["Tema"] == "Saúde"
    assert df.iloc[0]["id_materia"] == 7051  # mais recente primeiro


def test_vereadores_expoem_so_contato_institucional():
    df = nz.normalizar_vereadores(PARLAMENTARES, {40: "PSD"}, BASE)
    assert "telefone" not in [c.lower() for c in df.columns]
    emails = dict(zip(df["id_parlamentar"], df["E-mail institucional"]))
    assert emails[40] == "acacia@lagarto.se.leg.br"
    assert emails[41] == ""
    assert df.iloc[0]["Em exercício"]  # ativos primeiro


def test_votacoes_filtram_periodo_e_extraem_resultado():
    df_mat = nz.normalizar_materias(MATERIAS, nz.mapa_tipos(TIPOS), {}, {}, BASE)
    df = nz.normalizar_votacoes(VOTACOES, df_mat, "2026-01-01", "2026-12-31")
    assert len(df) == 1
    assert df.iloc[0]["Matéria"] == "IND 2/2026"
    assert df.iloc[0]["Resultado"] == "Aprovado"


# --- Serviço -------------------------------------------------------------------------

def test_carregar_camara_ponta_a_ponta():
    cli = SaplClient(BASE, session=FakeSession(_rotas_padrao()), pausa=0)
    dados = carregar_camara(BASE, date(2026, 1, 1), date(2026, 3, 1), client=cli)
    assert len(dados.materias) == 2
    assert len(dados.vereadores) == 2
    assert len(dados.votacoes) == 1
    assert dados.avisos == []


def test_carregar_camara_avisa_lacunas_sem_quebrar():
    rotas = _rotas_padrao()
    rotas["sessao/registrovotacao/"] = []
    sess = FakeSession(rotas, falhar={"parlamentares/filiacao/"})
    dados = carregar_camara(BASE, date(2026, 1, 1), date(2026, 3, 1), client=SaplClient(BASE, session=sess, pausa=0))
    assert len(dados.materias) == 2
    assert dados.materias["Partido"].eq("").all()
    assert any("filiações" in a for a in dados.avisos)
    assert any("votações" in a for a in dados.avisos)


def test_votacoes_enviam_fim_do_periodo_sem_T():
    sess = FakeSession(_rotas_padrao())
    SaplClient(BASE, session=sess, pausa=0).votacoes("2026-08-01", "2026-10-29")
    caminho, params = sess.chamadas[0]
    assert caminho == "sessao/registrovotacao/"
    assert params["data_hora__gte"] == "2026-08-01"
    assert params["data_hora__lte"] == "2026-10-29 23:59:59"


def test_falha_nas_votacoes_nao_vira_aviso_de_camara_sem_votacao():
    sess = FakeSession(_rotas_padrao(), falhar={"sessao/registrovotacao/"})
    dados = carregar_camara(BASE, date(2026, 1, 1), date(2026, 3, 1), client=SaplClient(BASE, session=sess, pausa=0))
    assert dados.votacoes_indisponiveis
    assert dados.votacoes.empty
    assert any("Não foi possível obter as votações" in a for a in dados.avisos)
    assert not any("não registrou votações" in a for a in dados.avisos)


def test_carregar_camara_propaga_falha_nas_materias():
    sess = FakeSession(_rotas_padrao(), falhar={"materia/materialegislativa/"})
    with pytest.raises(SaplErro):
        carregar_camara(BASE, date(2026, 1, 1), date(2026, 3, 1), client=SaplClient(BASE, session=sess, pausa=0))


# --- QA municipal --------------------------------------------------------------------

def _df_materias():
    return nz.normalizar_materias(
        MATERIAS, nz.mapa_tipos(TIPOS), nz.mapa_autores(AUTORES, PARLAMENTARES), {40: "PSD"}, BASE
    )


def test_prompt_municipal_recupera_e_rotula_refs():
    prompt, fontes, ids, codigos = municipal_qa.montar_prompt_municipal(
        _df_materias(), "Lagarto", "O que o vereador pediu sobre saúde na câmara?"
    )
    assert ids[0] == "M1"
    assert fontes.iloc[0]["id_materia"] == 7051  # a matéria de saúde vem primeiro
    assert codigos[0] == "7051"
    assert "Câmara Municipal de Lagarto" in prompt
    assert "[M2]" in prompt and "IND 2/2026" in prompt


def test_gerar_resposta_municipal_registra_trace(monkeypatch):
    registrado = {}

    def fake_trace(pergunta, ids, resposta, origem, fontes_codigos=None):
        registrado.update(origem=origem, ids=ids, codigos=fontes_codigos, resposta=resposta)

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="Foi pedida a reabertura do posto [M1]."))])
    )))
    monkeypatch.setattr(municipal_qa, "client", fake_client)
    monkeypatch.setattr(municipal_qa, "_registrar_trace", fake_trace)

    out = municipal_qa.gerar_resposta_municipal(_df_materias(), "Lagarto", "posto de saúde")
    assert registrado["origem"] == "municipal"
    assert extrair_ids_citados(out["resposta"]) == ["M1"]
    assert "M1" in registrado["ids"]
    assert "Link" in out["colunas_fonte"]
