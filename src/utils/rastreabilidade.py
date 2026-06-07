"""Métricas de rastreabilidade resposta→fonte a partir do log de trace.

Núcleo reutilizável pelo CLI (`scripts/avaliar_rastreabilidade.py`) e pela interface
(`src/app/app_streamlit.py`). Trabalha sobre o JSONL gerado por consulta
(`logs/qa_trace.jsonl`), uma linha por pergunta, com os campos:
`origem`, `pergunta`, `fontes_ids`, `n_fontes`, `resposta`.

Métricas (sobre o conjunto de respostas registradas):
- Cobertura de recuperação: proporção de consultas que recuperaram ao menos 1 fonte.
- Cobertura de citação: proporção de respostas que citam ao menos 1 id de fonte
  ([id] entre colchetes) que esteja entre as fontes efetivamente recuperadas.
- Precisão de citação: ids citados válidos / total de ids citados.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACE_PADRAO = ROOT / "logs" / "qa_trace.jsonl"

# Captura ids citados na resposta no formato [D3], [V1], [12345] etc.
_PADRAO_CITACAO = re.compile(r"\[([A-Za-z]?\d+)\]")


def carregar_registros(caminho: Path) -> list[dict]:
    """Lê o JSONL de trace, ignorando linhas vazias/inválidas."""
    caminho = Path(caminho)
    if not caminho.exists():
        return []
    registros = []
    # utf-8-sig descarta um eventual BOM no início do arquivo.
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return registros


def avaliar(registros: list[dict]) -> dict:
    """Calcula as 3 métricas de rastreabilidade sobre os registros."""
    total = len(registros)
    if total == 0:
        return {"total": 0}

    com_fontes = 0
    com_citacao_valida = 0
    ids_citados_total = 0
    ids_citados_validos = 0

    for reg in registros:
        fontes = set(str(x) for x in reg.get("fontes_ids", []))
        if fontes:
            com_fontes += 1

        citados = set(_PADRAO_CITACAO.findall(reg.get("resposta", "")))
        ids_citados_total += len(citados)
        validos = citados & fontes
        ids_citados_validos += len(validos)
        if validos:
            com_citacao_valida += 1

    return {
        "total": total,
        "cobertura_recuperacao": com_fontes / total,
        "cobertura_citacao": com_citacao_valida / total,
        "precisao_citacao": (ids_citados_validos / ids_citados_total) if ids_citados_total else 0.0,
        "ids_citados_total": ids_citados_total,
        "ids_citados_validos": ids_citados_validos,
    }


def avaliar_por_origem(registros: list[dict]) -> dict[str, dict]:
    """Segmenta os registros pelo campo `origem` e avalia cada grupo.

    Retorna {origem: métricas}. Registros sem `origem` caem em "desconhecida".
    """
    grupos: dict[str, list[dict]] = {}
    for reg in registros:
        origem = reg.get("origem") or "desconhecida"
        grupos.setdefault(origem, []).append(reg)
    return {origem: avaliar(regs) for origem, regs in grupos.items()}
