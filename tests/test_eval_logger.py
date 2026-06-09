"""Testes para src/utils/eval_logger.py (logger de avaliação comparativa de modelos)."""

import csv

import pytest

from src.utils.eval_logger import HEADER, EvalLogger, _Row


def test_header_casa_com_campos_da_row():
    # A ordem do CSV depende de HEADER; os campos da dataclass devem cobrir HEADER.
    assert list(_Row.__dataclass_fields__) == HEADER


def test_integridade_e_alucinacao_por_linha():
    log = EvalLogger(model="m", quant="Q4", temperature=0.1, seed=42)
    row = log.record(
        pergunta_id="Q01", tipo="Factual direta",
        resposta="Conforme [D1] e [D2], mas [D9] não existe.",
        ids_recuperados=["D1", "D2", "D3"],
        ids_citados=["D1", "D2", "D9"],
        corpus_ids={"D1", "D2", "D3"},
        tem_resposta_no_corpus="Sim",
    )
    assert row.total_citacoes == 3
    assert row.citacoes_validas == 2          # D1, D2 válidos; D9 fora do conjunto
    assert row.alucinacao == 1                # D9 não está no corpus_ids
    assert row.recusou_correto == ""          # só se aplica quando tem_resposta == "Nao"


def test_sem_alucinacao_quando_todas_validas():
    log = EvalLogger(model="m")
    row = log.record(
        pergunta_id="Q02", tipo="Factual direta", resposta="[D1]",
        ids_recuperados=["D1"], ids_citados=["D1"], corpus_ids={"D1"},
        tem_resposta_no_corpus="Sim",
    )
    assert row.alucinacao == 0
    assert row.citacoes_validas == 1


def test_alucinacao_override():
    log = EvalLogger(model="m")
    row = log.record(
        pergunta_id="Q03", tipo="Factual direta", resposta="Sem citação.",
        ids_recuperados=["D1"], ids_citados=[], corpus_ids={"D1"},
        tem_resposta_no_corpus="Sim", alucinacao_override=1,
    )
    assert row.alucinacao == 1


@pytest.mark.parametrize("tem_resposta,citou,esperado", [
    ("Nao", False, "1"),    # não há resposta e o modelo não citou => recusou certo
    ("Nao", True, "0"),     # não há resposta mas citou algo => não recusou
    ("não", False, "1"),    # aceita acento
    ("Sim", False, ""),     # não se aplica
    ("Parcial", True, ""),  # não se aplica
])
def test_recusou_correto(tem_resposta, citou, esperado):
    log = EvalLogger(model="m")
    ids = ["D1"] if citou else []
    row = log.record(
        pergunta_id="Q", tipo="Sem resposta no corpus", resposta="x",
        ids_recuperados=["D1"], ids_citados=ids, corpus_ids={"D1"},
        tem_resposta_no_corpus=tem_resposta,
    )
    assert row.recusou_correto == esperado


def test_run_id_incrementa():
    log = EvalLogger(model="m", run_prefix="r")
    r1 = log.record("Q1", "t", "[D1]", ["D1"], ["D1"], {"D1"}, "Sim")
    r2 = log.record("Q2", "t", "[D1]", ["D1"], ["D1"], {"D1"}, "Sim")
    assert (r1.run_id, r2.run_id) == ("r001", "r002")


def test_latencia_e_tokens_por_s():
    log = EvalLogger(model="m")
    t = log.start()
    t.mark_first_token()
    row = log.record(
        "Q", "t", "[D1]", ["D1"], ["D1"], {"D1"}, "Sim",
        tokens_gerados=100, timer=t,
    )
    assert isinstance(row.latencia_1tok_s, float)
    assert row.latencia_1tok_s >= 0
    assert isinstance(row.tokens_por_s, float)
    assert row.tokens_por_s > 0


def test_to_csv_cabecalho_e_ordem(tmp_path):
    log = EvalLogger(model="mistral", quant="Q4_K_M", temperature=0.1, seed=42)
    log.record("Q01", "Factual direta", "Resposta [D1].",
               ["D1", "D2"], ["D1"], {"D1", "D2"}, "Sim", tokens_gerados=50)
    saida = tmp_path / "coleta.csv"
    log.to_csv(str(saida))

    with saida.open(encoding="utf-8") as f:
        linhas = list(csv.reader(f))
    assert linhas[0] == HEADER
    row = dict(zip(HEADER, linhas[1]))
    assert row["modelo"] == "mistral"
    assert row["quantizacao"] == "Q4_K_M"
    assert row["ids_recuperados"] == "D1;D2"
    assert row["ids_citados"] == "D1"
    assert row["citacoes_validas"] == "1"
    assert row["total_citacoes"] == "1"
    assert row["temperatura"] == "0.1"
    assert row["seed"] == "42"


def test_summary():
    log = EvalLogger(model="m")
    log.record("Q1", "t", "[D1]", ["D1"], ["D1"], {"D1"}, "Sim")
    log.record("Q2", "t", "[D9]", ["D1"], ["D9"], {"D1"}, "Sim")
    s = log.summary()
    assert s["n"] == 2
    assert s["taxa_alucinacao"] == pytest.approx(0.5)
    assert s["integridade_referencial"] == pytest.approx(0.5)  # 1 válida / 2 citadas


def test_summary_vazio():
    assert EvalLogger(model="m").summary() == {"n": 0}
