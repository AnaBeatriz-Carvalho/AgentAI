"""Loader robusto das coletas da avaliação de geração (`resultados/geracao/coleta_*.csv`).

As coletas foram recuperadas do histórico e NÃO têm formato uniforme:
- Gemma/Llama/Qwen: CSV delimitado por vírgula, `resposta_gerada` entre aspas e os ids
  num único campo (juntados por `;`). Parse padrão.
- Mistral: delimitado por `;`, com `;` também dentro da resposta (sem aspas consistentes).
  Reconstrói-se por varredura reversa: os 10 últimos campos são fixos
  (`citacoes_validas..timestamp`) e, antes deles, um bloco de ids `Dk`/`Vk`; o restante,
  do 6º campo até o início do bloco de ids, é a resposta.

O separador entre `ids_recuperados` e `ids_citados` é dado por `total_citacoes`: os
últimos `total_citacoes` ids do bloco são os citados; os anteriores, os recuperados.

Uso:
    from src.eval.carregar_geracao import carregar_coletas
    linhas = carregar_coletas("resultados/geracao")  # -> list[dict], 160 respostas
"""

from __future__ import annotations

import csv
import glob
import os
import re
from pathlib import Path

FIXOS = [
    "citacoes_validas", "total_citacoes", "alucinacao", "recusou_correto",
    "latencia_1tok_s", "tokens_por_s", "vram_gb", "temperatura", "seed", "timestamp",
]
_ID = re.compile(r"^[DV]\d+$")


def _split_ids(texto: str) -> list[str]:
    return [x for x in re.split(r"[;,]", texto or "") if x.strip()]


def _linha(lead, resp, ids_rec, ids_cit, fixos) -> dict:
    return {
        "run_id": lead[0],
        "modelo": lead[1],
        "quantizacao": lead[2],
        "pergunta_id": lead[3],
        "tipo": lead[4],
        "resposta_gerada": (resp or "").strip(),
        "ids_recuperados": ids_rec,
        "ids_citados": ids_cit,
        "citacoes_validas": fixos[0],
        "total_citacoes": fixos[1],
        "alucinacao": fixos[2],
        "recusou_correto": fixos[3],
        "latencia_1tok_s": fixos[4],
        "tokens_por_s": fixos[5],
        "vram_gb": fixos[6],
        "temperatura": fixos[7],
        "seed": fixos[8],
        "timestamp": fixos[9],
    }


def carregar_coleta(path: str | Path) -> list[dict]:
    path = str(path)
    with open(path, encoding="utf-8-sig", newline="") as f:
        cabecalho = f.readline()
    semi = cabecalho.count(";") > cabecalho.count(",")
    linhas: list[dict] = []

    if not semi:  # CSV vírgula limpo
        with open(path, encoding="utf-8-sig", newline="") as f:
            for d in csv.DictReader(f):
                lead = [d["run_id"], d["modelo"], d.get("quantizacao", ""),
                        d["pergunta_id"], d["tipo"]]
                fixos = [d.get(c, "") for c in FIXOS]
                linhas.append(_linha(lead, d["resposta_gerada"],
                                     _split_ids(d["ids_recuperados"]),
                                     _split_ids(d["ids_citados"]), fixos))
        return linhas

    # Mistral: ';'-delimitado, varredura reversa
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f, delimiter=";", quotechar='"')
        next(r)  # cabeçalho
        for raw in r:
            if not raw:
                continue
            fixos = raw[-10:]
            corpo = raw[:-10]
            lead = corpo[0:5]
            k = len(corpo)
            while k > 5 and _ID.match((corpo[k - 1] or "").strip()):
                k -= 1
            bloco = [x.strip() for x in corpo[k:]]
            resp = ";".join(corpo[5:k])
            tot = int(fixos[1]) if str(fixos[1]).strip() not in ("", "None") else 0
            ids_cit = bloco[len(bloco) - tot:] if tot > 0 else []
            ids_rec = bloco[:len(bloco) - tot] if tot > 0 else bloco
            linhas.append(_linha(lead, resp, ids_rec, ids_cit, fixos))
    return linhas


def carregar_coletas(diretorio: str | Path = "resultados/geracao") -> list[dict]:
    linhas: list[dict] = []
    for path in sorted(glob.glob(os.path.join(str(diretorio), "coleta_*.csv"))):
        linhas.extend(carregar_coleta(path))
    return linhas


if __name__ == "__main__":
    ls = carregar_coletas()
    print(f"{len(ls)} respostas de {len(set(l['modelo'] for l in ls))} modelos")
