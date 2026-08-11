"""Avaliação de qualidade factual do agente conversacional (dimensão 4.3).

Gera cenários de pergunta cuja **resposta-verdade é computada deterministicamente** do
corpus (SQLite), roda o AGENTE REAL (``gerar_resposta_discurso`` — a mesma lógica do chat
do app, headless) e atribui um **veredito automático** por presença dos fatos-chave na
resposta: correta / parcialmente correta / incorreta / não respondida.

O veredito automático é **preliminar**: o CSV traz uma coluna ``veredito_revisado`` em
branco para a revisão humana ajustar os casos de fronteira (paráfrase, número escrito por
extenso etc.). A métrica-alvo é a **% de respostas corretas (≥70%)**.

Corpus: discursos de senadores de um período fixo; a mesma tabela é usada para computar a
verdade E alimentar o agente (garante coerência). ``Tema`` é atribuído pelo baseline
(igual à produção). LLM pela config do ``.env`` (LM Studio).

Uso::

    python3 scripts/avaliar_factual.py                       # maio/2026
    python3 scripts/avaliar_factual.py --inicio 2026-05-01 --fim 2026-05-31
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval.categorias import classificar_keyword
from src.ai.local_llm_handler import gerar_resposta_discurso

SAIDA_PADRAO = Path("resultados/factual/avaliacao_factual.csv")

# Padrões que indicam recusa/não-resposta do agente.
_RECUSA = ["nao consegui", "desculpe", "nao ha dados", "dificuldade", "reformule"]

# Frases (já normalizadas) que indicam ausência do item perguntado — usadas nos
# vereditos "nulo" (parlamentar inexistente) e "negativo" (UF ausente).
_AUSENCIA = ["nenhum", "nao aparece", "nao figura", "nao consta", "nao ha registro",
             "nao foi identificado", "nao esta presente", "nao ha discursos", "nao fez",
             "nao identifiquei", "nao encontrei", "zero discurso", "nao ha senador"]


def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _carregar_df(caminho_db: str, inicio: str, fim: str) -> pd.DataFrame:
    con = db.conectar(caminho_db)
    rows = con.execute(
        "SELECT codigo_pronunciamento, data, nome_autor, partido, uf, resumo "
        "FROM discursos WHERE tipo_autor LIKE 'Senador%' AND data BETWEEN ? AND ? "
        "AND TRIM(COALESCE(resumo,''))<>''",
        (inicio, fim),
    ).fetchall()
    con.close()
    df = pd.DataFrame([{
        "id_discurso": r["codigo_pronunciamento"],
        "Data": r["data"],
        "Parlamentar": r["nome_autor"],
        "Partido": r["partido"],
        "UF": r["uf"],
        "Resumo": r["resumo"],
    } for r in rows])
    if df.empty:
        return df
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Tema"] = df["Resumo"].map(classificar_keyword)
    return df


def _sobrenome(nome: str) -> str:
    toks = [t for t in _norm(nome).split() if len(t) > 2]
    return toks[-1] if toks else _norm(nome)


def _construir_cenarios(df: pd.DataFrame) -> list[dict]:
    """Cria cenários com verdade computada do df. Cada um tem: pergunta, tipo, checagem.

    Só entram perguntas **respondíveis** pelo que o agente recebe (estatísticas agregadas
    top-7 + fontes recuperadas), exceto casos propositais de limite (contagem de distintos,
    parlamentar inexistente) que testam alucinação.
    """
    vc = df["Parlamentar"].value_counts()
    total = len(df)
    n_sen = df["Parlamentar"].nunique()
    min_d, max_d = df["Data"].min().date(), df["Data"].max().date()
    ufs_presentes = set(df["UF"].dropna().unique())
    uf_ausente = next((u for u in ["AC", "AP", "RR", "TO", "SE", "PB"] if u not in ufs_presentes), "ZZ")

    cen = [
        {"tipo": "agregado", "pergunta": "Quantos discursos há no total nesta amostra?",
         "checagem": "numero", "esperado": total},
        {"tipo": "periodo", "pergunta": "Qual o intervalo de datas (primeira e última) dos discursos desta amostra?",
         "checagem": "ambos", "esperado": [str(min_d.year), str(max_d.year)],
         "esperado_exibicao": f"{min_d} a {max_d}"},
        {"tipo": "ranking", "pergunta": "Qual senador mais discursou no período?",
         "checagem": "texto", "esperado": _sobrenome(vc.index[0]), "esperado_exibicao": vc.index[0]},
        {"tipo": "ranking", "pergunta": "Quantos discursos fez o senador que mais discursou?",
         "checagem": "numero", "esperado": int(vc.iloc[0])},
        {"tipo": "ranking", "pergunta": "Cite os dois senadores mais ativos (que mais discursaram) nesta amostra.",
         "checagem": "ambos", "esperado": [_sobrenome(vc.index[0]), _sobrenome(vc.index[1])],
         "esperado_exibicao": f"{vc.index[0]} e {vc.index[1]}"},
        # Limite proposital: contagem de distintos não é dada ao agente → testa alucinação.
        {"tipo": "limite", "pergunta": "Quantos senadores diferentes discursaram no período?",
         "checagem": "numero", "esperado": n_sen,
         "esperado_exibicao": f"{n_sen} (info NÃO fornecida ao agente — testa alucinação)"},
        {"tipo": "alucinacao", "pergunta": "Quantos discursos o senador Fulano de Tal Inexistente fez nesta amostra?",
         "checagem": "nulo", "esperado_exibicao": "nenhum / não consta"},
        # Limite: partido mais ativo — contagem por partido NÃO é injetada no prompt.
        {"tipo": "limite", "pergunta": "Qual partido teve mais discursos nesta amostra?",
         "checagem": "texto", "esperado": _norm(df["Partido"].value_counts().index[0]),
         "esperado_exibicao": f"{df['Partido'].value_counts().index[0]} (info NÃO injetada — testa limite)"},
    ]
    # Filtro negativo só entra se existir uma UF REAL ausente do recorte (evita código falso).
    if uf_ausente != "ZZ":
        cen.append({"tipo": "filtro",
                    "pergunta": f"Algum senador do estado {uf_ausente} discursou nesta amostra?",
                    "checagem": "negativo", "esperado_exibicao": f"não ({uf_ausente} ausente)"})

    # Contagens específicas dos senadores do top-7 (o agente recebe esses números).
    for pos in range(1, min(6, len(vc))):
        nome = vc.index[pos]
        cen.append({
            "tipo": "especifico",
            "pergunta": f"Quantos discursos o(a) senador(a) {nome} fez nesta amostra?",
            "checagem": "numero", "esperado": int(vc.iloc[pos]),
        })

    # Filtros positivos: partidos/UFs efetivamente presentes.
    for partido in list(df["Partido"].value_counts().index[:2]):
        cen.append({"tipo": "filtro",
                    "pergunta": f"Há discursos de senadores do partido {partido} nesta amostra?",
                    "checagem": "afirmativo", "esperado_exibicao": f"sim ({partido} presente)"})
    uf_top = df["UF"].value_counts().index[0]
    cen.append({"tipo": "filtro",
                "pergunta": f"Algum senador do estado {uf_top} discursou nesta amostra?",
                "checagem": "afirmativo", "esperado_exibicao": f"sim ({uf_top} presente)"})

    # Conteúdo (grounding): o esperado é o CONJUNTO de senadores que realmente falaram do
    # tema — a resposta é correta se citar qualquer um deles.
    termos_tema = ["saúde", "educação", "segurança", "trabalho", "economia",
                   "meio ambiente", "orçamento", "violência"]
    for termo in termos_tema:
        sub = df[df["Resumo"].map(_norm).str.contains(_norm(termo))]
        if len(sub) < 2:
            continue
        conjunto = sorted({_sobrenome(n) for n in sub["Parlamentar"].unique()})
        exemplos = list(sub["Parlamentar"].unique())[:3]
        cen.append({
            "tipo": "conteudo",
            "pergunta": f"Algum discurso desta amostra trata de {termo}? Cite o senador.",
            "checagem": "texto_conjunto", "esperado_conjunto": conjunto,
            "esperado_exibicao": f"qualquer de: {', '.join(exemplos)}… ({len(sub)} discursos)",
        })

    return cen


def _checar_fato(r: str, cen: dict) -> tuple[str, bool]:
    """Veredito baseado apenas na presença do fato-chave na resposta normalizada `r`."""
    chk = cen["checagem"]
    if chk == "numero":
        esp = str(cen["esperado"])
        return ("correta", True) if esp in r else ("incorreta", False)
    if chk == "texto":
        esp = _norm(cen["esperado"])
        return ("correta", True) if esp in r else ("incorreta", False)
    if chk == "texto_conjunto":
        # Correta se citar QUALQUER senador que realmente discursou sobre o tema.
        return ("correta", True) if any(_norm(s) in r for s in cen["esperado_conjunto"]) else ("incorreta", False)
    if chk == "negativo":
        return ("correta", True) if any(nx in r for nx in _AUSENCIA) else ("incorreta", False)
    if chk == "ambos":
        achados = [e for e in cen["esperado"] if _norm(e) in r]
        if len(achados) == len(cen["esperado"]):
            return "correta", True
        if achados:
            return "parcialmente_correta", True
        return "incorreta", False
    if chk == "afirmativo":
        # Nega presença só com frases ESPECÍFICAS sobre discursos (evita casar "não há
        # informações sobre o total…", que não nega a presença).
        nega = ["nao ha discursos", "nenhum senador", "nao existe discurso", "nao ha senador",
                "nao encontrei discursos", "nao foram encontrados", "nao ha registro de discurso"]
        return ("incorreta", False) if any(n in r for n in nega) else ("correta", True)
    if chk == "nulo":
        return ("correta", True) if any(z in r for z in _AUSENCIA) else ("incorreta", False)
    return "incorreta", False


def _veredito(resposta: str, cen: dict) -> tuple[str, bool]:
    """(veredito, fato_encontrado). Checa o FATO primeiro; só então distingue recusa de erro.

    Isso evita falso-negativo quando a resposta está correta mas contém, de passagem, uma
    expressão de negação em outra oração. Preliminar — sujeito à revisão humana no CSV.
    """
    r = _norm(resposta)
    if not r:
        return ("correta", True) if cen["checagem"] in ("nulo", "negativo") else ("nao_respondida", False)

    veredito, achou = _checar_fato(r, cen)
    if veredito in ("correta", "parcialmente_correta"):
        return veredito, achou

    # Fato ausente: se o agente recusou explicitamente, marca "não respondida"
    # (exceto quando o esperado é justamente ausência — aí a recusa já foi tratada acima).
    if any(p in r for p in _RECUSA):
        return "nao_respondida", False
    return veredito, achou


def main() -> None:
    ap = argparse.ArgumentParser(description="Avaliação de qualidade factual (dimensão 4.3).")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--inicio", default="2026-05-01")
    ap.add_argument("--fim", default="2026-05-31")
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    args = ap.parse_args()

    df = _carregar_df(args.db, args.inicio, args.fim)
    if df.empty:
        print("Nenhum discurso de senador no período. Ajuste --inicio/--fim.")
        return
    print(f"Corpus: {len(df)} discursos de senadores, {df['Parlamentar'].nunique()} senadores, "
          f"{args.inicio}..{args.fim}\n")

    cenarios = _construir_cenarios(df)
    resultados = []
    from collections import Counter
    contagem = Counter()
    for i, cen in enumerate(cenarios, start=1):
        try:
            # temperature=0 → avaliação reprodutível (o app roda em 0.2; diferença anotada).
            resp = gerar_resposta_discurso(df, cen["pergunta"], temperature=0.0)["resposta"]
        except Exception as e:
            resp = f"[ERRO: {e}]"
        veredito, achou = _veredito(resp, cen)
        contagem[veredito] += 1
        resultados.append({
            "id": i, "tipo": cen["tipo"], "pergunta": cen["pergunta"],
            "resposta_esperada": cen.get("esperado_exibicao", cen.get("esperado")),
            "resposta_agente": resp.replace("\n", " ").strip(),
            "veredito_auto": veredito, "fato_encontrado": "sim" if achou else "não",
            "veredito_revisado": "",
        })
        print(f"  [{i:2}/{len(cenarios)}] {cen['tipo']:11} → {veredito}")

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(resultados[0].keys()))
        w.writeheader()
        w.writerows(resultados)

    n = len(resultados)
    corretas = contagem["correta"]
    parciais = contagem["parcialmente_correta"]
    pct_correta = corretas / n
    pct_com_parcial = (corretas + 0.5 * parciais) / n
    resumo = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "periodo": {"inicio": args.inicio, "fim": args.fim},
        "n_cenarios": n,
        "distribuicao": dict(contagem),
        "pct_corretas": round(pct_correta, 4),
        "pct_corretas_com_meia_parcial": round(pct_com_parcial, 4),
        "meta": 0.70,
        "atingiu_meta": pct_correta >= 0.70,
        "nota": "Veredito automático preliminar — revisar coluna veredito_revisado no CSV.",
    }
    saida.with_suffix(".resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== DIMENSÃO 4.3 — QUALIDADE FACTUAL (preliminar, automático) ===")
    print(f"  cenários: {n}  |  distribuição: {dict(contagem)}")
    print(f"  % CORRETAS: {pct_correta*100:.1f}%  (meta ≥70% → {'ATINGIU' if pct_correta>=0.70 else 'ABAIXO'})")
    print(f"  % corretas (parcial=0,5): {pct_com_parcial*100:.1f}%")
    print(f"\n✅ CSV p/ revisão: {saida}\n   Resumo: {saida.with_suffix('.resumo.json')}")
    print("  ⚠️  Revise 'veredito_revisado' nos casos de fronteira antes do número final.")


if __name__ == "__main__":
    main()
