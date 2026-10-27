"""Recalcula a tabela da avaliação de geração (4 modelos) a partir dos artefatos versionados.

Entradas (em `resultados/geracao/`):
- `coleta_*.csv`                   colunas automáticas (integridade, alucinação, tokens/s)
- `anotacao_geracao.csv`           anotação humana cega (rodada 1)
- `_chave_modelos.csv`             anotacao_id -> modelo (desanonimização)
- `anotacao_geracao_reteste.csv`   opcional: reanotação de ~30% (Kappa intra-anotador)
- `juiz_geracao.csv`               opcional: notas de suporte do LLM-juiz

Saídas (em `resultados/geracao/`):
- `metricas_geracao.json`          tudo consolidado
- `comparativo_geracao.csv`        uma linha por modelo
- `tabela_comparativo_modelos.tex` linhas prontas para o quadro `tab:comparativo_modelos`

Uso:
    python scripts/metricas_geracao.py                # exige anotação completa
    python scripts/metricas_geracao.py --parcial      # aceita anotação incompleta (prévia)
    python scripts/metricas_geracao.py --so-automaticas
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.carregar_geracao import carregar_coletas  # noqa: E402

GDIR = ROOT / "resultados" / "geracao"

ORDEM_MODELOS = [
    ("mistralai/mistral-7b-instruct-v0.3", "Mistral 7B Instruct v0.3"),
    ("qwen2.5-7b-instruct-1m", "Qwen2.5 7B Instruct"),
    ("meta-llama-3.1-8b-instruct", "Llama 3.1 8B Instruct"),
    ("gemma-2-9b-it", "Gemma 2 9B Instruct"),
]
NOME = dict(ORDEM_MODELOS)

FAIXAS = {"suporte_semantico": (1, 4), "pt_formal": (1, 5), "completude": (1, 5)}


# ---------------------------------------------------------------- leitura

def ler_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _num(v) -> float | None:
    s = str(v if v is not None else "").strip().replace(",", ".")
    if s in ("", "None", "nan", "n/a"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def validar_anotacao(linhas: list[dict]) -> tuple[list[str], dict]:
    """Retorna (erros, contagem de preenchimento por coluna)."""
    erros, preench = [], Counter()
    for r in linhas:
        aid = r.get("anotacao_id", "?")
        for col, (lo, hi) in FAIXAS.items():
            v = _num(r.get(col))
            if v is None:
                continue
            preench[col] += 1
            if not (lo <= v <= hi) or v != int(v):
                erros.append(f"{aid}: {col}={r.get(col)!r} fora de {lo}..{hi}")
        rec = str(r.get("recusa_correta", "")).strip()
        sem_resp = str(r.get("tem_resposta_no_corpus", "")).strip() == "Não"
        if sem_resp:
            if rec in ("0", "1"):
                preench["recusa_correta"] += 1
            elif rec:
                erros.append(f"{aid}: recusa_correta={rec!r} deve ser 0 ou 1")
        elif rec not in ("", "n/a"):
            erros.append(f"{aid}: recusa_correta preenchida em pergunta com resposta no corpus")
    return erros, dict(preench)


# ---------------------------------------------------------------- estatística

def kappa(a: list, b: list, ponderado: bool = False, categorias=None) -> float | None:
    """Kappa de Cohen (ponderado quadrático opcional), sem dependências externas."""
    pares = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pares) < 2:
        return None
    cats = sorted(categorias or {v for p in pares for v in p})
    k = len(cats)
    if k < 2:
        return None
    idx = {c: i for i, c in enumerate(cats)}
    n = len(pares)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in pares:
        obs[idx[x]][idx[y]] += 1
    ma = [sum(obs[i]) / n for i in range(k)]
    mb = [sum(obs[i][j] for i in range(k)) / n for j in range(k)]

    def w(i, j):
        if ponderado:
            return ((i - j) ** 2) / ((k - 1) ** 2)
        return 0.0 if i == j else 1.0

    do = sum(w(i, j) * obs[i][j] / n for i in range(k) for j in range(k))
    de = sum(w(i, j) * ma[i] * mb[j] for i in range(k) for j in range(k))
    if de == 0:
        return 1.0 if do == 0 else None
    return round(1 - do / de, 4)


def concordancia(a: list, b: list) -> dict:
    pares = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pares:
        return {"n": 0}
    xs, ys = zip(*pares)
    return {
        "n": len(pares),
        "concordancia_exata": round(sum(x == y for x, y in pares) / len(pares), 4),
        "concordancia_pm1": round(sum(abs(x - y) <= 1 for x, y in pares) / len(pares), 4),
        "kappa": kappa(list(xs), list(ys), categorias=[1, 2, 3, 4]),
        "kappa_ponderado_quadratico": kappa(list(xs), list(ys), ponderado=True, categorias=[1, 2, 3, 4]),
    }


def _media(vs):
    vs = [v for v in vs if v is not None]
    return round(statistics.mean(vs), 2) if vs else None


def _mediana(vs):
    vs = [v for v in vs if v is not None]
    return round(statistics.median(vs), 2) if vs else None


# ---------------------------------------------------------------- métricas

def metricas_automaticas(coletas: list[dict]) -> dict:
    por = defaultdict(list)
    for r in coletas:
        por[r["modelo"]].append(r)
    out = {}
    for modelo, rs in por.items():
        integ, aluc = [], []
        for r in rs:
            tot = _num(r["total_citacoes"]) or 0
            val = _num(r["citacoes_validas"]) or 0
            if tot > 0:
                integ.append(val / tot)
            a = _num(r["alucinacao"])
            if a is not None:
                aluc.append(a)
        sem_resp = [r for r in rs if str(r["tipo"]).lower().startswith("sem resposta")]
        out[modelo] = {
            "n": len(rs),
            "integridade_referencial": round(statistics.mean(integ), 4) if integ else None,
            "respostas_com_citacao": len(integ),
            "alucinacao_referencial": round(statistics.mean(aluc), 4) if aluc else None,
            "tokens_por_s_mediana": _mediana([_num(r["tokens_por_s"]) for r in rs]),
            "latencia_1tok_s_mediana": _mediana([_num(r["latencia_1tok_s"]) for r in rs]),
            "recusa_proxy_automatico": sum(_num(r["recusou_correto"]) == 1 for r in sem_resp),
            "n_sem_resposta": len(sem_resp),
        }
    return out


def metricas_humanas(anot: list[dict], chave: dict[str, str]) -> tuple[dict, dict]:
    por = defaultdict(list)
    for r in anot:
        por[chave[r["anotacao_id"]]].append(r)
    out, q04 = {}, {}
    for modelo, rs in por.items():
        rec = [str(r.get("recusa_correta", "")).strip() for r in rs
               if str(r.get("tem_resposta_no_corpus", "")).strip() == "Não"]
        out[modelo] = {
            "suporte_semantico_media": _media([_num(r["suporte_semantico"]) for r in rs]),
            "suporte_dist": dict(sorted(Counter(int(v) for v in
                                 (_num(r["suporte_semantico"]) for r in rs) if v is not None).items())),
            "recusa_correta": sum(v == "1" for v in rec),
            "recusa_anotadas": sum(v in ("0", "1") for v in rec),
            "pt_formal_media": _media([_num(r["pt_formal"]) for r in rs]),
            "completude_media": _media([_num(r["completude"]) for r in rs]),
        }
        for r in rs:
            if r["pergunta_id"] == "Q04":
                q04[modelo] = _num(r["suporte_semantico"])
    return out, q04


def _fmt(v, casas=2):
    if v is None:
        return "--"
    return f"{v:.{casas}f}".replace(".", "{,}")


def tabela_latex(auto: dict, hum: dict) -> str:
    linhas = [
        "% Gerado por scripts/metricas_geracao.py -- não editar à mão.",
        "% Colunas: Suporte sem. | Recusa (/8) | PT formal | Completude | Tokens/s | Integ. ref. | Alucinação",
    ]
    for stamp, nome in ORDEM_MODELOS:
        a, h = auto.get(stamp, {}), hum.get(stamp, {})
        rec = f"{h['recusa_correta']}/{a.get('n_sem_resposta', 8)}" if h.get("recusa_anotadas") else "--"
        tps = a.get("tokens_por_s_mediana")
        linhas.append(" & ".join([
            nome,
            _fmt(h.get("suporte_semantico_media")),
            rec,
            _fmt(h.get("pt_formal_media")),
            _fmt(h.get("completude_media")),
            _fmt(tps, 1 if tps and tps >= 10 else 2),
            _fmt(a.get("integridade_referencial")),
            _fmt(a.get("alucinacao_referencial")),
        ]) + r" \\")
    return "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(GDIR))
    ap.add_argument("--parcial", action="store_true", help="aceita anotação incompleta (prévia)")
    ap.add_argument("--so-automaticas", action="store_true")
    args = ap.parse_args()
    d = Path(args.dir)

    coletas = carregar_coletas(d)
    auto = metricas_automaticas(coletas)
    res: dict = {"n_respostas": len(coletas), "automaticas": auto}

    if not args.so_automaticas:
        anot = ler_csv(d / "anotacao_geracao.csv")
        chave = {r["anotacao_id"]: r["modelo"] for r in ler_csv(d / "_chave_modelos.csv")}
        erros, preench = validar_anotacao(anot)
        res["preenchimento"] = preench
        if erros:
            print("Erros de anotação:\n  " + "\n  ".join(erros[:30]))
            return 2
        esperado = {"suporte_semantico": len(anot), "pt_formal": len(anot),
                    "completude": len(anot), "recusa_correta": 32}
        faltando = {c: n - preench.get(c, 0) for c, n in esperado.items() if preench.get(c, 0) < n}
        if faltando and not args.parcial:
            print(f"Anotação incompleta (faltam {faltando}). Use --parcial para uma prévia.")
            return 3
        res["anotacao_completa"] = not faltando
        hum, q04 = metricas_humanas(anot, chave)
        res["humanas"] = hum
        res["q04_suporte_por_modelo"] = q04

        ret_path = d / "anotacao_geracao_reteste.csv"
        if ret_path.exists():
            r1 = {r["anotacao_id"]: r for r in anot}
            ret = [r for r in ler_csv(ret_path) if _num(r.get("suporte_semantico")) is not None]
            ids = [r["anotacao_id"] for r in ret if r["anotacao_id"] in r1]
            rr = {r["anotacao_id"]: r for r in ret}
            res["intra_anotador"] = {
                col: concordancia([_num(r1[i][col]) for i in ids], [_num(rr[i].get(col)) for i in ids])
                for col in ("suporte_semantico",)
            }

        juiz_path = d / "juiz_geracao.csv"
        if juiz_path.exists():
            jz = {r["anotacao_id"]: _num(r.get("suporte_juiz")) for r in ler_csv(juiz_path)}
            ids = [r["anotacao_id"] for r in anot]
            res["humano_x_juiz"] = concordancia([_num(r["suporte_semantico"]) for r in anot],
                                                [jz.get(i) for i in ids])
            jm = defaultdict(list)
            for i in ids:
                jm[chave[i]].append(jz.get(i))
            res["juiz_media_por_modelo"] = {m: _media(v) for m, v in jm.items()}
    else:
        hum = {}

    (d / "metricas_geracao.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(d / "comparativo_geracao.csv", "w", encoding="utf-8", newline="") as f:
        cols = ["modelo", "suporte_semantico_media", "recusa_correta", "recusa_proxy_automatico",
                "pt_formal_media", "completude_media", "tokens_por_s_mediana",
                "integridade_referencial", "alucinacao_referencial"]
        w = csv.writer(f)
        w.writerow(cols)
        for stamp, nome in ORDEM_MODELOS:
            a, h = auto.get(stamp, {}), hum.get(stamp, {})
            w.writerow([nome] + [h.get(c, a.get(c)) for c in cols[1:]])
    (d / "tabela_comparativo_modelos.tex").write_text(tabela_latex(auto, hum), encoding="utf-8")

    print(json.dumps({k: v for k, v in res.items() if k != "automaticas"}, ensure_ascii=False, indent=1)[:3000])
    for stamp, nome in ORDEM_MODELOS:
        a = auto.get(stamp, {})
        print(f"{nome:28s} integ={a.get('integridade_referencial')} aluc={a.get('alucinacao_referencial')} "
              f"tok/s={a.get('tokens_por_s_mediana')} recusa_proxy={a.get('recusa_proxy_automatico')}/{a.get('n_sem_resposta')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
