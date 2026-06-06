"""Avalia a rastreabilidade das respostas do chatbot a partir do log de trace.

Lê o JSONL gerado por consulta (logs/qa_trace.jsonl) e calcula, sobre o conjunto de
respostas registradas:

- Cobertura de recuperação: proporção de consultas que recuperaram ao menos 1 fonte.
- Cobertura de citação: proporção de respostas que citam ao menos 1 id de fonte
  ([id_discurso] entre colchetes) que esteja entre as fontes efetivamente recuperadas.
- Precisão de citação: proporção das citações que correspondem a fontes recuperadas
  (ids citados válidos / total de ids citados).

Uso:
    python scripts/avaliar_rastreabilidade.py [caminho_do_jsonl]
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACE_PADRAO = ROOT / "logs" / "qa_trace.jsonl"

# Captura ids citados na resposta no formato [D3], [12345] etc.
_PADRAO_CITACAO = re.compile(r"\[([A-Za-z]?\d+)\]")


def carregar_registros(caminho: Path) -> list[dict]:
    if not caminho.exists():
        print(f"Arquivo de trace não encontrado: {caminho}")
        return []
    registros = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError:
            continue
    return registros


def avaliar(registros: list[dict]) -> dict:
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


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else TRACE_PADRAO
    registros = carregar_registros(caminho)
    m = avaliar(registros)

    if m.get("total", 0) == 0:
        print("Nenhum registro para avaliar.")
        return 1

    print(f"Arquivo: {caminho}")
    print(f"Consultas avaliadas: {m['total']}")
    print(f"Cobertura de recuperação (≥1 fonte): {m['cobertura_recuperacao']:.1%}")
    print(f"Cobertura de citação (≥1 id válido citado): {m['cobertura_citacao']:.1%}")
    print(f"Precisão de citação (ids válidos/citados): {m['precisao_citacao']:.1%}"
          f" ({m['ids_citados_validos']}/{m['ids_citados_total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
