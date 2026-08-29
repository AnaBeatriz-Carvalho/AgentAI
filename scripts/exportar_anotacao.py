"""Exporta a amostra estratificada de discursos para anotação humana (gabarito, 4.2).

Gera o CSV que o anotador único preencherá (passada 1), seguindo o
`protocolo-anotacao-AgentAI.md` (Seção 5). Decisões fixadas:

- **População:** discursos de autores Senador(a) com ``Resumo`` não-vazio, deduplicados
  por conteúdo (mesmo ``Resumo`` aparece uma vez só).
- **Estratificação:** por rótulo provisório do baseline por palavras-chave — usado apenas
  como *frame* de amostragem para garantir cobertura de todas as categorias. O rótulo do
  baseline **não vai no CSV** (evita ancoragem do anotador); é recomputável de forma
  determinística por ``src.eval.categorias.classificar_keyword`` na hora de calcular as
  métricas baseline×gabarito.
- **Base textual:** o ``Resumo`` — o mesmo input que o baseline e o Mistral classificam,
  para uma comparação justa contra o gabarito.
- **Reprodutibilidade:** amostragem com semente fixa; um manifesto registra semente, n por
  categoria, contagem total e período do corpus.

Uso::

    python3 scripts/exportar_anotacao.py            # n=18/cat, seed=42
    python3 scripts/exportar_anotacao.py --n-por-categoria 15 --seed 7
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval.categorias import CATEGORIAS, classificar_keyword

SAIDA_PADRAO = Path("resultados/gabarito/anotacao_discursos.csv")
COLUNAS_CSV = ["id_discurso", "data", "parlamentar", "resumo", "categoria", "confianca", "observacao"]


def _carregar_populacao(con: sqlite3.Connection) -> list[dict]:
    """Senadores com Resumo não-vazio, deduplicados por conteúdo (mantém o 1º código)."""
    rows = con.execute(
        "SELECT codigo_pronunciamento, data, nome_autor, resumo "
        "FROM discursos "
        "WHERE tipo_autor LIKE 'Senador%' AND TRIM(COALESCE(resumo,'')) <> '' "
        "ORDER BY data, codigo_pronunciamento"
    ).fetchall()
    vistos: set[str] = set()
    populacao: list[dict] = []
    for r in rows:
        resumo = r["resumo"].strip()
        chave = resumo.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        populacao.append({
            "id_discurso": r["codigo_pronunciamento"],
            "data": r["data"],
            "parlamentar": r["nome_autor"],
            "resumo": resumo,
        })
    return populacao


def exportar(caminho_db: str, n_por_categoria: int, seed: int, saida: Path) -> None:
    con = db.conectar(caminho_db)
    populacao = _carregar_populacao(con)

    # Estratifica pela predição do baseline (frame de amostragem, não vai ao CSV).
    estratos: dict[str, list[dict]] = {c: [] for c in CATEGORIAS}
    for reg in populacao:
        estratos[classificar_keyword(reg["resumo"])].append(reg)

    rng = random.Random(seed)
    selecionados: list[dict] = []
    resumo_estrato: dict[str, int] = {}
    for cat in CATEGORIAS:
        pool = estratos[cat]
        k = min(n_por_categoria, len(pool))
        amostra = rng.sample(pool, k) if k < len(pool) else list(pool)
        resumo_estrato[cat] = len(amostra)
        selecionados.extend(amostra)

    # Embaralha a ordem final para intercalar categorias (reduz ancoragem na anotação).
    rng.shuffle(selecionados)

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS_CSV)
        w.writeheader()
        for reg in selecionados:
            w.writerow({
                "id_discurso": reg["id_discurso"],
                "data": reg["data"],
                "parlamentar": reg["parlamentar"],
                "resumo": reg["resumo"],
                "categoria": "",
                "confianca": "",
                "observacao": "",
            })

    periodo = con.execute(
        "SELECT MIN(data), MAX(data) FROM discursos WHERE tipo_autor LIKE 'Senador%' AND data<>''"
    ).fetchone()
    con.close()

    manifesto = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "n_por_categoria_alvo": n_por_categoria,
        "n_total": len(selecionados),
        "populacao_elegivel": len(populacao),
        "periodo_corpus_senadores": {"min": periodo[0], "max": periodo[1]},
        "n_por_estrato_baseline": resumo_estrato,
        "base_textual": "resumo",
        "categorias": CATEGORIAS,
        "arquivo_csv": str(saida),
        "observacao": (
            "Estratos calculados pelo baseline de palavras-chave (frame de amostragem). "
            "O rotulo verdadeiro e definido pela anotacao humana no campo 'categoria'."
        ),
    }
    caminho_manifesto = saida.with_suffix(".manifesto.json")
    caminho_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Exportado: {saida}  ({len(selecionados)} discursos)")
    print(f"   Manifesto: {caminho_manifesto}")
    print(f"   População elegível (senador, resumo não-vazio, dedup): {len(populacao)}")
    print("   n por estrato (frame baseline):")
    for cat in CATEGORIAS:
        print(f"     {cat:24} {resumo_estrato[cat]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Exporta amostra estratificada para anotação.")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--n-por-categoria", type=int, default=18)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    args = ap.parse_args()
    exportar(args.db, args.n_por_categoria, args.seed, Path(args.saida))


if __name__ == "__main__":
    main()
