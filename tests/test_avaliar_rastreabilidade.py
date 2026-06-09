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


class TestExtrairIdsCitados:
    """Extração de ids citados, incluindo normalização de citação agrupada."""

    def test_um_id_por_colchete(self):
        assert rast.extrair_ids_citados("Conforme [D1] e [D2], mas não [D9].") == ["D1", "D2", "D9"]

    def test_citacao_agrupada_virgula(self):
        # O ponto desta tarefa: [D1, D2, D5] vira três citações.
        assert rast.extrair_ids_citados("...com três discursos [D1, D2, D5].") == ["D1", "D2", "D5"]

    def test_citacao_agrupada_ponto_e_virgula(self):
        assert rast.extrair_ids_citados("[V1; V2;V3]") == ["V1", "V2", "V3"]

    def test_mistura_agrupado_e_isolado(self):
        assert rast.extrair_ids_citados("[D1, D2] e também [D5]") == ["D1", "D2", "D5"]

    def test_nao_confunde_prosa_com_citacao(self):
        # Colchete com prosa não é citação; não deve extrair o "1958".
        assert rast.extrair_ids_citados("o Projeto de Lei nº 1958 [Projeto de Lei nº 1958]") == []

    def test_codigos_numericos(self):
        assert rast.extrair_ids_citados("[12345] e [522046, 522043]") == ["12345", "522046", "522043"]

    def test_parentese_estrito_captura(self):
        # (D1)/(D12) entre parênteses contam (padrão estrito letra+dígitos).
        assert rast.extrair_ids_citados("Eduardo Girão (D1) discursou; ver também (D12).") == ["D1", "D12"]

    def test_parentese_nao_captura_numero_solto(self):
        # Datas, percentuais e números soltos em prosa NÃO viram citação.
        assert rast.extrair_ids_citados("no ano (2025) o tema foi 13% (13%) e a PEC (66)") == []

    def test_parentese_agrupado_estrito(self):
        assert rast.extrair_ids_citados("conforme (D1, D2) e (D5)") == ["D1", "D2", "D5"]

    def test_parentese_com_prosa_nao_captura(self):
        # "(PEC 66)" tem espaço entre letras e dígitos: não é citação.
        assert rast.extrair_ids_citados("a proposta (PEC 66) e a (Lei 1958)") == []

    def test_colchete_e_parentese_juntos(self):
        assert rast.extrair_ids_citados("um [D1] e outro (D2)") == ["D1", "D2"]

    def test_vazio(self):
        assert rast.extrair_ids_citados("") == []
        assert rast.extrair_ids_citados("sem citações aqui") == []
