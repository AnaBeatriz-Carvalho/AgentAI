"""CLI: avalia a rastreabilidade das respostas do chatbot a partir do log de trace.

A lógica de cálculo vive em `src/utils/rastreabilidade.py` (reutilizada também pela
interface). Este script é apenas o wrapper de linha de comando.

Uso:
    python scripts/avaliar_rastreabilidade.py [caminho_do_jsonl]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.rastreabilidade import TRACE_PADRAO, avaliar, carregar_registros


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else TRACE_PADRAO
    registros = carregar_registros(caminho)
    m = avaliar(registros)

    if m.get("total", 0) == 0:
        print("Nenhum registro para avaliar.")
        return 1

    print(f"Arquivo: {caminho}")
    print(f"Consultas avaliadas: {m['total']}")
    print(f"Cobertura de recuperação (>=1 fonte): {m['cobertura_recuperacao']:.1%}")
    print(f"Cobertura de citação (>=1 id válido citado): {m['cobertura_citacao']:.1%}")
    print(f"Precisão de citação (ids válidos/citados): {m['precisao_citacao']:.1%}"
          f" ({m['ids_citados_validos']}/{m['ids_citados_total']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
