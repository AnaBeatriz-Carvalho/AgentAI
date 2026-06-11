"""Utilidades compartilhadas do experimento de classificacao tematica (clausula (a)).

Fonte unica da taxonomia (`eval/classificacao/taxonomia.json`): rotulos, definicoes e
dicionario de palavras-chave do Baseline 1. Mantem prompt do Mistral, baseline keyword e
metricas alinhados ao MESMO conjunto de rotulos, evitando divergencia entre scripts.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVAL_DIR = ROOT / "eval"
CLASSIF_DIR = EVAL_DIR / "classificacao"
TAXONOMIA_PATH = CLASSIF_DIR / "taxonomia.json"
SNAPSHOT_CSV = EVAL_DIR / "corpus_snapshot.csv"

# Artefatos do experimento (predicoes e gabarito).
GABARITO_TEMPLATE = CLASSIF_DIR / "gabarito_para_anotar.csv"
GABARITO_CSV = CLASSIF_DIR / "gabarito.csv"
PRED_MISTRAL = CLASSIF_DIR / "pred_mistral.csv"
PRED_KEYWORD = CLASSIF_DIR / "pred_keyword.csv"
PRED_TFIDF = CLASSIF_DIR / "pred_tfidf.csv"

COL_ID = "id_discurso"
COL_GOLD = "tema_gold"


def normalizar(texto: str) -> str:
    """Minusculas + remocao de acentos (casa termos independente de acentuacao)."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def carregar_taxonomia() -> dict:
    return json.loads(TAXONOMIA_PATH.read_text(encoding="utf-8"))


def rotulos(taxonomia: dict | None = None) -> list[str]:
    """Lista canonica de rotulos (ordem fixa para matrizes/relatorios)."""
    tx = taxonomia or carregar_taxonomia()
    return list(tx["rotulos"])


def rotulo_canonico(valor: str, taxonomia: dict | None = None) -> str | None:
    """Mapeia um rotulo digitado (com/sem acento, caixa variavel) ao rotulo canonico.

    Permite anotar `tema_gold` em portugues natural (ex.: "Politica e Instituicoes" com
    acentos) sem quebrar o casamento com os rotulos canonicos do codigo. Retorna None se
    o valor nao corresponde a nenhum rotulo (invalido) ou e vazio.
    """
    alvo = normalizar(valor).strip()
    if not alvo:
        return None
    tx = taxonomia or carregar_taxonomia()
    for rot in rotulos(tx):
        if normalizar(rot) == alvo:
            return rot
    return None


def _keywords_por_rotulo(taxonomia: dict) -> dict[str, list[str]]:
    return {
        rot: [normalizar(k) for k in dados.get("keywords", [])]
        for rot, dados in taxonomia["macrocategorias"].items()
    }


def classificar_keyword(resumo: str, taxonomia: dict | None = None) -> str:
    """Baseline 1: vence o rotulo com mais palavras-chave casadas; empate zero -> Outros.

    Piso minimo sem aprendizado. Deterministico. Conta termos distintos do dicionario
    presentes no resumo normalizado; em empate, mantem a ordem de `rotulos` (estavel).
    """
    tx = taxonomia or carregar_taxonomia()
    texto = normalizar(resumo)
    kws = _keywords_por_rotulo(tx)
    melhor, melhor_cont = "Outros", 0
    for rot in rotulos(tx):
        palavras = kws.get(rot, [])
        cont = sum(1 for p in palavras if p and p in texto)
        if cont > melhor_cont:
            melhor, melhor_cont = rot, cont
    return melhor if melhor_cont > 0 else "Outros"
