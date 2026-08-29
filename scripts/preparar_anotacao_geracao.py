"""Monta o CSV de ANOTAÇÃO CEGA da avaliação de geração (Fase 1 do plano).

A partir das coletas recuperadas (`resultados/geracao/coleta_*.csv`), das perguntas
(`perguntas.json`) e do corpus congelado (`corpus_snapshot.csv`), gera:

- `resultados/geracao/anotacao_geracao.csv`  -> planilha de anotação, EMBARALHADA e
  SEM o nome do modelo (cega). Traz pergunta, tipo, se há resposta no corpus, a evidência
  gold já resolvida do corpus e a resposta gerada; colunas de nota em branco.
- `resultados/geracao/_chave_modelos.csv`    -> chave anotacao_id -> modelo/run_id/pergunta
  (NÃO abrir durante a anotação; usada só para desanonimizar no cálculo das métricas).

A anotação julga o SUPORTE SEMÂNTICO contra a evidência gold da pergunta (conforme o
protocolo do artigo), não contra os ids posicionais [D1..Dn].

Uso:
    python scripts/preparar_anotacao_geracao.py            # semente 42
    python scripts/preparar_anotacao_geracao.py --seed 7
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.eval.carregar_geracao import carregar_coletas

GDIR = ROOT / "resultados" / "geracao"


def _norm_tem_resposta(v: str) -> str:
    s = str(v).strip().lower()
    if s in ("nao", "não", "no", "n"):
        return "Não"
    if s in ("sim", "yes", "s"):
        return "Sim"
    if s in ("parcial", "partial", "p"):
        return "Parcial"
    return str(v).strip()


def _carregar_perguntas() -> dict[str, dict]:
    dados = json.loads((GDIR / "perguntas.json").read_text(encoding="utf-8-sig"))
    ps = dados.get("perguntas", dados) if isinstance(dados, dict) else dados
    out = {}
    for p in ps:
        pid = p.get("id")
        if not pid:
            continue
        out[pid] = {
            "texto": p.get("texto") or p.get("pergunta", ""),
            "tipo": p.get("tipo", ""),
            "tem_resposta": _norm_tem_resposta(p.get("tem_resposta_no_corpus") or p.get("tem_resposta", "")),
            "gold_ids": str(p.get("gold_ids", "") or ""),
            "obs": p.get("obs", ""),
        }
    return out


def _resolver_gold(gold_ids: str, corpus: pd.DataFrame) -> str:
    """Resolve apenas ids numéricos de discurso contra o snapshot. Para gold não-id
    ('(varios)', '-'), a evidência de referência vem do campo `obs` (nota GOLD)."""
    ids = [x.strip() for x in gold_ids.replace(";", ",").split(",")
           if x.strip() and x.strip().isdigit()]
    if not ids:
        return ""
    idx = corpus.set_index(corpus["id_discurso"].astype(str))
    partes = []
    for gid in ids:
        if gid in idx.index:
            r = idx.loc[gid]
            if hasattr(r, "iloc") and getattr(r, "ndim", 1) > 1:
                r = r.iloc[0]
            resumo = str(r.get("Resumo", ""))[:260]
            partes.append(f"[{gid}] {r.get('Parlamentar','?')} ({r.get('Data','?')}, tema {r.get('Tema','?')}): {resumo}")
        else:
            partes.append(f"[{gid}] (id não encontrado no snapshot)")
    return " || ".join(partes)


def _tem_anotacao_preenchida(path: Path) -> bool:
    """True se o CSV de anotação já existe com alguma nota preenchida (evita sobrescrever)."""
    if not path.exists():
        return False
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter=";"):
                for col in ("suporte_semantico", "pt_formal", "completude"):
                    if str(row.get(col, "")).strip():
                        return True
                if str(row.get("recusa_correta", "")).strip() not in ("", "n/a"):
                    return True
    except Exception:
        return True  # na dúvida, protege
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true",
                    help="Sobrescreve anotacao_geracao.csv mesmo com notas já preenchidas.")
    args = ap.parse_args()

    anot_existente = GDIR / "anotacao_geracao.csv"
    if _tem_anotacao_preenchida(anot_existente) and not args.force:
        raise SystemExit(
            f"ABORTADO: {anot_existente} já contém anotação preenchida.\n"
            "Regenerar apagaria as notas. Use --force só se tiver certeza (faça backup antes)."
        )

    respostas = carregar_coletas(GDIR)
    if len(respostas) != 160:
        print(f"[aviso] esperava 160 respostas, obtive {len(respostas)}")
    perguntas = _carregar_perguntas()
    corpus = pd.read_csv(GDIR / "corpus_snapshot.csv")

    # Cache da evidência gold por pergunta (não recomputar 4x).
    gold_cache = {pid: _resolver_gold(p["gold_ids"], corpus) for pid, p in perguntas.items()}

    registros = []
    for r in respostas:
        pid = r["pergunta_id"]
        p = perguntas.get(pid, {})
        registros.append({
            "modelo": r["modelo"],
            "run_id": r["run_id"],
            "pergunta_id": pid,
            "tipo": p.get("tipo", r["tipo"]),
            "tem_resposta_no_corpus": p.get("tem_resposta", ""),
            "pergunta": p.get("texto", ""),
            "gold_nota": p.get("obs", ""),
            "gold_evidencia": gold_cache.get(pid, ""),
            "resposta_gerada": r["resposta_gerada"],
        })

    random.Random(args.seed).shuffle(registros)

    anot_path = GDIR / "anotacao_geracao.csv"
    chave_path = GDIR / "_chave_modelos.csv"
    campos_anot = [
        "anotacao_id", "pergunta_id", "tipo", "tem_resposta_no_corpus",
        "pergunta", "gold_nota", "gold_evidencia", "resposta_gerada",
        "suporte_semantico", "recusa_correta", "pt_formal", "completude", "observacao",
    ]
    with open(anot_path, "w", encoding="utf-8-sig", newline="") as fa, \
         open(chave_path, "w", encoding="utf-8-sig", newline="") as fk:
        wa = csv.DictWriter(fa, fieldnames=campos_anot, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        wk = csv.DictWriter(fk, fieldnames=["anotacao_id", "modelo", "run_id", "pergunta_id"], delimiter=";")
        wa.writeheader()
        wk.writeheader()
        for i, reg in enumerate(registros, 1):
            aid = f"A{i:03d}"
            # recusa_correta só se aplica às perguntas SEM resposta no corpus.
            recusa_default = "" if reg["tem_resposta_no_corpus"] == "Não" else "n/a"
            wa.writerow({
                "anotacao_id": aid,
                "pergunta_id": reg["pergunta_id"],
                "tipo": reg["tipo"],
                "tem_resposta_no_corpus": reg["tem_resposta_no_corpus"],
                "pergunta": reg["pergunta"],
                "gold_nota": reg["gold_nota"],
                "gold_evidencia": reg["gold_evidencia"],
                "resposta_gerada": reg["resposta_gerada"],
                "suporte_semantico": "",
                "recusa_correta": recusa_default,
                "pt_formal": "",
                "completude": "",
                "observacao": "",
            })
            wk.writerow({"anotacao_id": aid, "modelo": reg["modelo"],
                         "run_id": reg["run_id"], "pergunta_id": reg["pergunta_id"]})

    print(f"OK: {len(registros)} linhas")
    print(f"  anotação (cega): {anot_path}")
    print(f"  chave (não abrir): {chave_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
