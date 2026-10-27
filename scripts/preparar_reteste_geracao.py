"""Monta a planilha de REANOTAÇÃO (teste-reteste) da avaliação de geração.

Sorteia ~30% das linhas de `anotacao_geracao.csv` (estratificado por tipo de pergunta,
semente fixa), reembaralha e grava `anotacao_geracao_reteste.csv` com as colunas de nota
EM BRANCO. As notas da rodada 1 não são copiadas, para que a reanotação seja cega.

Quando usar: só depois de 2 a 4 semanas da rodada 1 (intervalo de esquecimento).
O `scripts/metricas_geracao.py` calcula o Kappa intra-anotador automaticamente quando
encontra este arquivo preenchido.

Uso:
    python scripts/preparar_reteste_geracao.py            # 30%, semente 2027
    python scripts/preparar_reteste_geracao.py --frac 0.3 --seed 2027
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GDIR = ROOT / "resultados" / "geracao"
NOTAS = ("suporte_semantico", "recusa_correta", "pt_formal", "completude", "observacao")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=2027)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    destino = GDIR / "anotacao_geracao_reteste.csv"
    if destino.exists() and not args.force:
        with open(destino, encoding="utf-8-sig", newline="") as f:
            if any(str(r.get("suporte_semantico", "")).strip() for r in csv.DictReader(f, delimiter=";")):
                raise SystemExit(f"ABORTADO: {destino} já tem notas. Use --force só com backup.")

    with open(GDIR / "anotacao_geracao.csv", encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f, delimiter=";")
        campos = rd.fieldnames
        linhas = list(rd)

    rnd = random.Random(args.seed)
    por_tipo = defaultdict(list)
    for r in linhas:
        por_tipo[r["tipo"]].append(r)
    amostra = []
    for tipo in sorted(por_tipo):
        grupo = por_tipo[tipo]
        k = max(1, round(len(grupo) * args.frac))
        amostra.extend(rnd.sample(grupo, k))
    rnd.shuffle(amostra)

    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, delimiter=";")
        w.writeheader()
        for r in amostra:
            novo = dict(r)
            for c in NOTAS:
                novo[c] = ""
            if r["tem_resposta_no_corpus"] != "Não":
                novo["recusa_correta"] = "n/a"
            w.writerow(novo)
    print(f"OK: {len(amostra)} linhas ({len(amostra)/len(linhas):.0%}) -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
