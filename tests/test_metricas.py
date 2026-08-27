"""Testes das funções puras de métrica de classificação (dimensão 4.2)."""

import sys
from pathlib import Path

import pytest

from src.eval import metricas as M

LABELS = ["A", "B", "C"]

# --- Acesso ao pipeline do script (fonte CSV, sem LLM/rede/SQLite) ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import metricas_classificacao as mc  # noqa: E402

GABARITO_ANOTADO = ROOT / "resultados/gabarito/anotacao_discursos_categorizado.csv"
GABARITO_VAZIO = ROOT / "resultados/gabarito/anotacao_discursos.csv"
PREDICOES_CSV = ROOT / "resultados/metricas/predicoes_classificacao_llm.csv"


def test_acuracia_perfeita():
    g = ["A", "B", "C"]
    assert M.acuracia(g, g) == 1.0


def test_precisao_revocacao_f1():
    # gold vs pred com um erro conhecido: um B previsto como A.
    gold = ["A", "A", "B", "B", "C"]
    pred = ["A", "A", "A", "B", "C"]
    r = M.metricas_por_categoria(gold, pred, LABELS)
    # A: tp=2, fp=1 -> precisao 2/3; revocacao 2/2=1
    assert r["por_categoria"]["A"]["precisao"] == round(2 / 3, 4)
    assert r["por_categoria"]["A"]["revocacao"] == 1.0
    # B: tp=1, fn=1 -> revocacao 1/2; precisao 1/1=1
    assert r["por_categoria"]["B"]["revocacao"] == 0.5
    assert r["por_categoria"]["B"]["precisao"] == 1.0
    assert r["acuracia"] == 0.8
    assert r["por_categoria"]["A"]["suporte"] == 2


def test_matriz_confusao():
    gold = ["A", "A", "B"]
    pred = ["A", "B", "B"]
    m = M.matriz_confusao(gold, pred, LABELS)
    assert m["A"]["A"] == 1
    assert m["A"]["B"] == 1
    assert m["B"]["B"] == 1


def test_cohen_kappa_perfeito_e_zero():
    g = ["A", "B", "A", "B"]
    assert M.cohen_kappa(g, g, LABELS) == 1.0
    # concordância só ao acaso tende a kappa ~0
    a = ["A", "A", "B", "B"]
    b = ["A", "B", "A", "B"]
    k = M.cohen_kappa(a, b, LABELS)
    assert -0.6 <= k <= 0.1


def test_macro_vs_weighted():
    gold = ["A", "A", "A", "B"]
    pred = ["A", "A", "A", "A"]  # nunca acerta B
    r = M.metricas_por_categoria(gold, pred, ["A", "B"])
    # B tem F1 0; A tem F1 alto -> macro < weighted (A domina o suporte)
    assert r["por_categoria"]["B"]["f1"] == 0.0
    assert r["weighted_f1"] >= r["macro_f1"]


def test_concordancia_simples():
    assert M.concordancia_simples(["A", "B"], ["A", "A"]) == 0.5
    assert M.concordancia_simples([], []) == 0.0


# --- Testes do pipeline metricas_classificacao (fonte CSV versionada) ---

def _macro_f1_reportaveis_por_modelo() -> dict[str, float]:
    """Reproduz o macro-F1 (8 categorias reportáveis) por classificador lendo os CSV
    versionados — mesmo cálculo do script, sem SQLite/LLM/rede."""
    ids, resumos = mc._ids_e_resumos(GABARITO_ANOTADO)
    llm_por_modelo = mc._llm_preds_csv(PREDICOES_CSV)
    preds = mc._predicoes(resumos, llm_por_modelo, ids)
    gold_map = mc._carregar_gabarito(GABARITO_ANOTADO)
    gold_ids = list(gold_map.keys())

    out: dict[str, float] = {}
    for nome, mp in preds.items():
        ids_val = [i for i in gold_ids if mp.get(i) is not None]
        gold = [gold_map[i] for i in ids_val]
        pred = [mp[i] for i in ids_val]
        met = mc.M.metricas_por_categoria(gold, pred, mc.CATEGORIAS)
        macro8 = sum(met["por_categoria"][c]["f1"] for c in mc.CATEGORIAS_REPORTAVEIS) / len(
            mc.CATEGORIAS_REPORTAVEIS
        )
        out[nome] = macro8
    return out


def test_reprodutibilidade_macro_f1_fonte_csv():
    """Calculando pela fonte CSV default, o macro-F1(8) por modelo bate com o esperado."""
    esperado = {
        "Mistral-7B": 0.750,
        "Gemma-2-9B": 0.699,
        "Baseline-KW": 0.596,
        "Llama-3.1-8B": 0.384,
    }
    obtido = _macro_f1_reportaveis_por_modelo()
    for modelo, alvo in esperado.items():
        assert modelo in obtido, f"classificador ausente: {modelo}"
        assert abs(obtido[modelo] - alvo) < 1e-3, (modelo, obtido[modelo], alvo)


def test_guard_gabarito_sem_categorias_aborta(tmp_path, monkeypatch):
    """Gabarito sem categorias → SystemExit != 0 e nenhum arquivo de saída gerado."""
    saida = tmp_path / "out_nao_deve_existir"
    monkeypatch.setattr(
        sys, "argv",
        ["metricas_classificacao.py",
         "--gabarito", str(GABARITO_VAZIO),
         "--saida", str(saida)],
    )
    with pytest.raises(SystemExit) as exc:
        mc.main()
    assert exc.value.code != 0
    assert not saida.exists()  # abortou antes de criar qualquer saída
