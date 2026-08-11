"""Testes das funções puras de métrica de classificação (dimensão 4.2)."""

from src.eval import metricas as M

LABELS = ["A", "B", "C"]


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
