"""Métricas de classificação para a dimensão 4.2 (funções puras, sem dependências).

Implementadas à mão (sem scikit-learn) para manter o projeto leve e 100% reprodutível.
Trabalham sobre listas alinhadas de rótulos verdadeiros (``gold``) e previstos (``pred``),
restritas a um conjunto fixo de ``labels`` (a taxonomia das 10 categorias).

Fornece o que o artigo precisa para comparar os classificadores lado a lado:
- ``metricas_por_categoria``: precisão, revocação e F1 por categoria + macro/weighted + acurácia.
- ``matriz_confusao``: contagens gold×pred.
- ``cohen_kappa``: concordância corrigida pelo acaso (classificador×gabarito e modelo×modelo).
"""

from __future__ import annotations

from collections import Counter


def acuracia(gold: list[str], pred: list[str]) -> float:
    if not gold:
        return 0.0
    return sum(1 for g, p in zip(gold, pred) if g == p) / len(gold)


def metricas_por_categoria(gold: list[str], pred: list[str], labels: list[str]) -> dict:
    """Precisão/revocação/F1 por categoria + suporte; agrega macro e weighted-F1.

    ``suporte`` é o nº de exemplos do gold naquela categoria. Categorias sem suporte e sem
    predição saem com métricas 0 (mantidas na tabela para o artigo ficar completo).
    """
    tp = Counter()
    fp = Counter()
    fn = Counter()
    suporte = Counter()
    for g, p in zip(gold, pred):
        suporte[g] += 1
        if g == p:
            tp[p] += 1
        else:
            fp[p] += 1
            fn[g] += 1

    por_cat = {}
    for c in labels:
        prec = tp[c] / (tp[c] + fp[c]) if (tp[c] + fp[c]) else 0.0
        rev = tp[c] / (tp[c] + fn[c]) if (tp[c] + fn[c]) else 0.0
        f1 = 2 * prec * rev / (prec + rev) if (prec + rev) else 0.0
        por_cat[c] = {
            "precisao": round(prec, 4),
            "revocacao": round(rev, 4),
            "f1": round(f1, 4),
            "suporte": suporte[c],
        }

    total = len(gold) or 1
    macro_f1 = sum(por_cat[c]["f1"] for c in labels) / len(labels) if labels else 0.0
    weighted_f1 = sum(por_cat[c]["f1"] * por_cat[c]["suporte"] for c in labels) / total

    return {
        "por_categoria": por_cat,
        "acuracia": round(acuracia(gold, pred), 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "n": len(gold),
    }


def matriz_confusao(gold: list[str], pred: list[str], labels: list[str]) -> dict:
    """Matriz gold×pred como dict aninhado {gold_label: {pred_label: contagem}}."""
    m = {g: {p: 0 for p in labels} for g in labels}
    for g, p in zip(gold, pred):
        if g in m and p in m[g]:
            m[g][p] += 1
    return m


def cohen_kappa(a: list[str], b: list[str], labels: list[str]) -> float:
    """Kappa de Cohen entre duas sequências de rótulos (classificador×gold ou modelo×modelo)."""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    ca = Counter(a)
    cb = Counter(b)
    pe = sum((ca[l] / n) * (cb[l] / n) for l in labels)
    if pe == 1.0:
        return 1.0
    return round((po - pe) / (1 - pe), 4)


def concordancia_simples(a: list[str], b: list[str]) -> float:
    """Proporção de posições em que a e b coincidem (agreement bruto)."""
    if not a:
        return 0.0
    return round(sum(1 for x, y in zip(a, b) if x == y) / len(a), 4)
