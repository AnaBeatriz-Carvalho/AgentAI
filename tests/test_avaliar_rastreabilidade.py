"""Testes para src/utils/rastreabilidade.py (métricas de rastreabilidade)."""

import pytest

from src.utils import rastreabilidade as rast


def test_total_zero_para_lista_vazia():
    assert rast.avaliar([]) == {"total": 0}


def test_metricas_em_conjunto_sintetico():
    """Replica o cenário validado no handoff: ~66,7% / 33,3% / 66,7%."""
    registros = [
        # 2 das 3 fontes citadas são válidas; 1 id ([D9]) é inválido.
        {"fontes_ids": ["D1", "D2"], "resposta": "Conforme [D1] e [D2], mas não [D9]."},
        # recuperou fonte, mas não citou.
        {"fontes_ids": ["D3"], "resposta": "Resposta sem citação."},
        # não recuperou fonte alguma.
        {"fontes_ids": [], "resposta": "Resposta genérica."},
    ]

    m = rast.avaliar(registros)

    assert m["total"] == 3
    assert m["cobertura_recuperacao"] == pytest.approx(2 / 3)
    assert m["cobertura_citacao"] == pytest.approx(1 / 3)
    assert m["precisao_citacao"] == pytest.approx(2 / 3)
    assert m["ids_citados_total"] == 3
    assert m["ids_citados_validos"] == 2


def test_precisao_zero_quando_sem_citacoes():
    registros = [{"fontes_ids": ["D1"], "resposta": "Sem ids citados."}]
    m = rast.avaliar(registros)
    assert m["precisao_citacao"] == 0.0


def test_carregar_registros_arquivo_inexistente(tmp_path):
    assert rast.carregar_registros(tmp_path / "nao_existe.jsonl") == []


def test_carregar_registros_ignora_bom_e_linhas_invalidas(tmp_path):
    arq = tmp_path / "trace.jsonl"
    conteudo = (
        '﻿{"origem": "discurso", "fontes_ids": ["D1"], "resposta": "[D1]"}\n'
        "linha invalida\n"
        "\n"
        '{"origem": "votacao", "fontes_ids": ["V1"], "resposta": "[V1]"}\n'
    )
    arq.write_text(conteudo, encoding="utf-8")
    registros = rast.carregar_registros(arq)
    assert len(registros) == 2


def test_avaliar_por_origem_segmenta():
    registros = [
        {"origem": "discurso", "fontes_ids": ["D1"], "resposta": "Conforme [D1]."},
        {"origem": "discurso", "fontes_ids": ["D2"], "resposta": "Sem citação."},
        {"origem": "votacao", "fontes_ids": ["V1"], "resposta": "Voto [V1]."},
    ]

    por_origem = rast.avaliar_por_origem(registros)

    assert set(por_origem) == {"discurso", "votacao"}
    assert por_origem["discurso"]["total"] == 2
    assert por_origem["discurso"]["cobertura_citacao"] == pytest.approx(1 / 2)
    assert por_origem["votacao"]["total"] == 1
    assert por_origem["votacao"]["cobertura_citacao"] == pytest.approx(1.0)


def test_avaliar_por_origem_sem_campo_origem():
    registros = [{"fontes_ids": ["D1"], "resposta": "[D1]"}]
    por_origem = rast.avaliar_por_origem(registros)
    assert "desconhecida" in por_origem
