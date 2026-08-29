"""Avaliação de rastreabilidade sobre o corpus real (dimensão 4.4).

Gera traces reais rodando consultas variadas pelo MESMO caminho do app
(``gerar_resposta_discurso``) e mede, contra o SQLite:

- **Cobertura de citação:** % das respostas que citam ao menos uma fonte válida quando
  deveriam (todas as consultas aqui são de conteúdo/grounding → deveriam citar).
- **Integridade referencial (métrica-meta ≥80%):** % das citações cujo ``ref`` aponta para
  uma fonte efetivamente recuperada e cujo ``id_discurso`` EXISTE no corpus. Mede integridade
  referencial — NÃO atribuição semântica (se o discurso sustenta a afirmação). A distinção é
  proposital (SLR do autor) e não é colapsada aqui.
- **Checagem de extrapolação:** (a) citações *dangling* — refs citados que não estão entre as
  fontes recuperadas (fonte inventada); (b) candidatos a incompatibilidade semântica — ref
  válido cuja frase citante não compartilha termos com o resumo da fonte (heurístico,
  reportado à parte, fora da métrica de integridade).

Persiste em ``resultados/rastreabilidade/`` os traces brutos (JSONL) e as métricas (JSON).

Uso::

    python3 scripts/avaliar_rastreabilidade_corpus.py
    python3 scripts/avaliar_rastreabilidade_corpus.py --inicio 2026-05-01 --fim 2026-05-31
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import db
from src.eval.categorias import classificar_keyword
from src.ai.local_llm_handler import gerar_resposta_discurso
from src.utils.rastreabilidade import _PADRAO_CITACAO

DIR_SAIDA = Path("resultados/rastreabilidade")
_STOP = {"para", "sobre", "como", "quais", "cite", "senador", "senadores", "discurso",
         "discursos", "amostra", "esta", "este", "fonte", "fontes", "algum", "houve"}


def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _termos(texto: str) -> set[str]:
    return {t for t in re.findall(r"\w{5,}", _norm(texto)) if t not in _STOP}


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
        "id_discurso": r["codigo_pronunciamento"], "Data": r["data"],
        "Parlamentar": r["nome_autor"], "Partido": r["partido"],
        "UF": r["uf"], "Resumo": r["resumo"],
    } for r in rows])
    if not df.empty:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
        df["Tema"] = df["Resumo"].map(classificar_keyword)
    return df


def _construir_consultas(df: pd.DataFrame) -> list[str]:
    """Consultas de conteúdo/grounding — todas deveriam citar fontes."""
    consultas = []
    temas = ["saúde", "educação", "segurança", "trabalho", "economia", "meio ambiente",
             "infraestrutura", "orçamento", "violência", "imposto", "energia", "agricultura"]
    for t in temas:
        consultas.append(f"Quais senadores discursaram sobre {t} e o que defenderam? Cite as fontes.")
    # Senadores mais ativos: sobre o que discursaram.
    for nome in list(df["Parlamentar"].value_counts().index[:10]):
        consultas.append(f"Sobre o que o senador {nome} discursou nesta amostra? Cite as fontes.")
    # Termos distintos extraídos de resumos reais.
    termos = ["reforma", "projeto de lei", "homenagem", "fronteira", "criança",
              "endividamento", "servidor", "eleição", "combustível", "moradia"]
    for termo in termos:
        consultas.append(f"Houve algum discurso mencionando {termo}? Cite o senador e a fonte.")
    return consultas


def _resolver(df_fontes: pd.DataFrame) -> dict[str, str]:
    """ref (D1..Dn) → id_discurso (codigo real), a partir das fontes recuperadas."""
    if df_fontes is None or df_fontes.empty or "ref" not in df_fontes.columns:
        return {}
    return dict(zip(df_fontes["ref"].astype(str), df_fontes["id_discurso"].astype(str)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Avaliação de rastreabilidade sobre o corpus (4.4).")
    ap.add_argument("--db", default=str(db.CAMINHO_DB_PADRAO))
    ap.add_argument("--inicio", default="2026-05-01")
    ap.add_argument("--fim", default="2026-05-31")
    args = ap.parse_args()

    df = _carregar_df(args.db, args.inicio, args.fim)
    if df.empty:
        print("Corpus vazio no período.")
        return

    # Conjunto de códigos existentes no corpus (verificação de existência contra o SQLite).
    con = db.conectar(args.db)
    codigos_corpus = {r[0] for r in con.execute("SELECT codigo_pronunciamento FROM discursos")}
    con.close()

    consultas = _construir_consultas(df)
    print(f"Corpus: {len(df)} discursos ({df['Parlamentar'].nunique()} senadores), "
          f"{args.inicio}..{args.fim}. Consultas: {len(consultas)}\n")

    traces = []
    for i, pergunta in enumerate(consultas, start=1):
        try:
            out = gerar_resposta_discurso(df, pergunta, temperature=0.0)
        except Exception as e:
            traces.append({"pergunta": pergunta, "erro": str(e)})
            print(f"  [{i:2}/{len(consultas)}] ERRO: {e}")
            continue
        resposta = out["resposta"]
        fontes_df = out["fontes_usadas"]
        ref2cod = _resolver(fontes_df)
        refs_disponiveis = set(ref2cod)

        citados = _PADRAO_CITACAO.findall(resposta)  # ex.: ['D3','D18']
        citados_unicos = list(dict.fromkeys(citados))
        validos = [c for c in citados_unicos if c in refs_disponiveis]
        dangling = [c for c in citados_unicos if c not in refs_disponiveis]
        # Integridade referencial: ref válido cujo código existe no corpus.
        existentes = [c for c in validos if ref2cod.get(c) in codigos_corpus]

        # Candidatos a incompatibilidade semântica (heurístico, fora da métrica de integridade):
        # frase que contém o ref não compartilha termos com o resumo da fonte citada.
        semantic_flags = []
        resumo_por_ref = {}
        if fontes_df is not None and not fontes_df.empty:
            resumo_por_ref = dict(zip(fontes_df["ref"].astype(str), fontes_df["Resumo"].astype(str)))
        for c in validos:
            frases = [f for f in re.split(r"(?<=[.!?])\s+", resposta) if f"[{c}]" in f]
            termos_frase = set().union(*[_termos(f) for f in frases]) if frases else set()
            termos_fonte = _termos(resumo_por_ref.get(c, ""))
            if termos_frase and termos_fonte and not (termos_frase & termos_fonte):
                semantic_flags.append(c)

        traces.append({
            "id": i, "pergunta": pergunta,
            "deve_citar": True,
            "n_fontes": len(ref2cod),
            "fontes_refs": list(ref2cod.keys()),
            "fontes_codigos": list(ref2cod.values()),
            "resposta": resposta,
            "citados": citados_unicos,
            "citados_validos": validos,
            "citados_dangling": dangling,
            "citados_existentes_corpus": existentes,
            "semantic_flags": semantic_flags,
        })
        marca = "ok" if (validos and not dangling) else ("dangling" if dangling else "sem-citação")
        print(f"  [{i:2}/{len(consultas)}] citados={citados_unicos or '-'} "
              f"validos={len(validos)} dangling={len(dangling)} → {marca}")

    # ---- Métricas ----
    validos_traces = [t for t in traces if "erro" not in t]
    n = len(validos_traces)
    com_citacao = sum(1 for t in validos_traces if t["citados_validos"])
    total_citacoes = sum(len(t["citados"]) for t in validos_traces)
    citacoes_integras = sum(len(t["citados_existentes_corpus"]) for t in validos_traces)
    total_dangling = sum(len(t["citados_dangling"]) for t in validos_traces)
    traces_com_dangling = [t for t in validos_traces if t["citados_dangling"]]
    traces_semantic = [t for t in validos_traces if t["semantic_flags"]]

    cobertura_citacao = com_citacao / n if n else 0.0
    integridade_referencial = citacoes_integras / total_citacoes if total_citacoes else 0.0

    metricas = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "periodo": {"inicio": args.inicio, "fim": args.fim},
        "n_traces": n,
        "total_citacoes": total_citacoes,
        "cobertura_citacao": round(cobertura_citacao, 4),
        "integridade_referencial": round(integridade_referencial, 4),
        "integridade_referencial_meta": 0.80,
        "atingiu_meta_integridade": integridade_referencial >= 0.80,
        "extrapolacao": {
            "definicao": "integridade referencial (existência no corpus), NÃO atribuição semântica",
            "citacoes_dangling": total_dangling,
            "traces_com_dangling": len(traces_com_dangling),
            "pct_traces_com_dangling": round(len(traces_com_dangling) / n, 4) if n else 0.0,
            "candidatos_incompatibilidade_semantica_traces": len(traces_semantic),
            "nota_semantica": "heurístico (overlap de termos frase×resumo); fora da métrica de integridade",
        },
    }

    DIR_SAIDA.mkdir(parents=True, exist_ok=True)
    (DIR_SAIDA / "traces_rastreabilidade.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in traces) + "\n", encoding="utf-8")
    (DIR_SAIDA / "metricas_rastreabilidade.json").write_text(
        json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== DIMENSÃO 4.4 — RASTREABILIDADE (n={n}) ===")
    print(f"  Cobertura de citação      : {cobertura_citacao*100:.1f}%  ({com_citacao}/{n})")
    print(f"  Integridade referencial   : {integridade_referencial*100:.1f}%  "
          f"({citacoes_integras}/{total_citacoes})  [meta ≥80% → "
          f"{'ATINGIU' if integridade_referencial>=0.80 else 'ABAIXO'}]")
    print(f"  (integridade referencial = citações que existem no corpus; NÃO atribuição semântica)")
    print(f"\n  Extrapolação:")
    print(f"    citações dangling (ref não recuperado): {total_dangling} "
          f"em {len(traces_com_dangling)} trace(s)")
    print(f"    candidatos a incompat. semântica (heurístico): {len(traces_semantic)} trace(s)")

    if traces_com_dangling:
        print(f"\n  Casos com citação dangling (fonte inventada):")
        for t in traces_com_dangling:
            print(f"    #{t['id']} dangling={t['citados_dangling']} (fontes disp.: {len(t['fontes_refs'])}) "
                  f"| {t['pergunta'][:60]}")
    if traces_semantic:
        print(f"\n  Candidatos a incompatibilidade semântica (frase×resumo sem termos comuns):")
        for t in traces_semantic:
            print(f"    #{t['id']} refs={t['semantic_flags']} | {t['pergunta'][:60]}")

    print(f"\n✅ Persistido em {DIR_SAIDA}/ (traces_rastreabilidade.jsonl, metricas_rastreabilidade.json)")


if __name__ == "__main__":
    main()
