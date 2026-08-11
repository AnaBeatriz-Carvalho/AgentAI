"""Classifica discursos com o LLM few-shot e persiste por modelo (dimensão 4.2, etapa 5).

Por padrão, classifica exatamente os discursos do gabarito (ids lidos do CSV de anotação),
garantindo que as predições do LLM fiquem alinhadas ao conjunto que será comparado contra o
rótulo humano. O resultado vai para a tabela ``classificacao_llm`` (chave discurso+modelo),
permitindo rodar vários modelos e comparar depois.

Requer o LM Studio (ou outro servidor OpenAI-compatível) ativo com o modelo carregado.

Exemplos::

    python3 scripts/classificar_llm.py                       # modelo do .env, ids do gabarito
    python3 scripts/classificar_llm.py --modelo google/gemma-2-9b-it
    python3 scripts/classificar_llm.py --forcar               # reclassifica os já feitos
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval import classificador_llm as clf
from src.config.settings import get_local_llm_config

CSV_GABARITO_PADRAO = Path("resultados/gabarito/anotacao_discursos.csv")


def _ids_do_gabarito(caminho: Path) -> list[str]:
    with Path(caminho).open(encoding="utf-8-sig", newline="") as fh:
        return [linha["id_discurso"] for linha in csv.DictReader(fh)]


def _resumo_por_id(con, ids: list[str]) -> dict[str, str]:
    marcadores = ",".join("?" * len(ids))
    rows = con.execute(
        f"SELECT codigo_pronunciamento, resumo FROM discursos WHERE codigo_pronunciamento IN ({marcadores})",
        ids,
    ).fetchall()
    return {r["codigo_pronunciamento"]: (r["resumo"] or "") for r in rows}


def main() -> None:
    ap = argparse.ArgumentParser(description="Classifica discursos com LLM few-shot.")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--gabarito", default=str(CSV_GABARITO_PADRAO),
                    help="CSV de onde ler os ids a classificar.")
    ap.add_argument("--modelo", default=None, help="Sobrescreve o modelo do .env.")
    ap.add_argument("--forcar", action="store_true",
                    help="Reclassifica discursos já classificados por este modelo.")
    ap.add_argument("--sleep", type=float, default=0.2, help="Pausa entre chamadas (s).")
    args = ap.parse_args()

    modelo = args.modelo or get_local_llm_config()["model"]
    ids = _ids_do_gabarito(args.gabarito)
    con = db.conectar(args.db)
    db.criar_schema(con)
    resumos = _resumo_por_id(con, ids)

    ja_feitos: set[str] = set()
    if not args.forcar:
        ja_feitos = {
            r[0] for r in con.execute(
                "SELECT id_discurso FROM classificacao_llm WHERE modelo=?", (modelo,)
            ).fetchall()
        }

    # Cliente único reaproveitado em todas as chamadas.
    client, modelo_cfg = clf._client_padrao()
    modelo = args.modelo or modelo_cfg

    pendentes = [i for i in ids if i not in ja_feitos]
    print(f"Modelo: {modelo} · prompt: {clf.PROMPT_VERSAO}")
    print(f"Discursos: {len(ids)} · já feitos: {len(ja_feitos)} · a classificar: {len(pendentes)}\n")

    from collections import Counter
    dist = Counter()
    for i, cod in enumerate(pendentes, start=1):
        cat = clf.classificar_llm(resumos.get(cod, ""), modelo=modelo, client=client)
        db.upsert_classificacao_llm(con, cod, modelo, cat, clf.PROMPT_VERSAO)
        dist[cat] += 1
        print(f"  [{i}/{len(pendentes)}] {cod} → {cat}")
        time.sleep(args.sleep)

    con.close()
    print("\n✅ Classificação concluída. Distribuição desta execução:")
    for cat, n in dist.most_common():
        print(f"   {cat:24} {n}")


if __name__ == "__main__":
    main()
