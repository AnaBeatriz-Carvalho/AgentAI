"""Interface de anotação guiada da avaliação de geração (uso local da anotadora).

Mostra um item por vez, com o gold ao lado da resposta, e conduz a anotação por
perguntas objetivas derivadas do codebook (`src/eval/rubrica_anotacao.py`). Grava as
notas no próprio CSV de anotação e o caminho de decisão em `<arquivo>_decisoes.csv`.
Não lê a chave dos modelos nem as notas do LLM-juiz.

Uso:
    streamlit run scripts/anotar_geracao.py
    streamlit run scripts/anotar_geracao.py -- --arquivo resultados/geracao/anotacao_geracao_reteste.csv
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from src.eval import rubrica_anotacao as rb  # noqa: E402

PADRAO = ROOT / "resultados" / "geracao" / "anotacao_geracao.csv"


def _args() -> Path:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arquivo", default=str(PADRAO))
    a, _ = ap.parse_known_args()
    p = Path(a.arquivo)
    return p if p.is_absolute() else ROOT / p


def _destacar(texto: str) -> str:
    """Negrito em números e anos para facilitar a conferência com o gold."""
    t = (texto or "").replace("$", "\\$")
    return re.sub(r"(?<![\w*])(\d[\d.,]*)", r"**\1**", t)


def _indice_inicial(linhas) -> int:
    for i, r in enumerate(linhas):
        if not rb.anotada(r):
            return i
    return 0


def main() -> None:
    st.set_page_config(page_title="Anotação guiada", layout="wide")
    arquivo = _args()
    if not arquivo.exists():
        st.error(f"Arquivo não encontrado: {arquivo}")
        return

    campos, linhas, term = rb.ler_planilha(arquivo)
    decisoes = rb.ler_decisoes(arquivo)
    n = len(linhas)
    feitas = sum(rb.anotada(r) for r in linhas)

    if "i" not in st.session_state:
        st.session_state.i = _indice_inicial(linhas)
    i = st.session_state.i
    r = linhas[i]
    aid = r["anotacao_id"]
    dec = decisoes.get(aid, {})
    sem = rb.sem_resposta(r["tem_resposta_no_corpus"])

    # ---- barra lateral
    with st.sidebar:
        st.markdown(f"**Arquivo:** `{arquivo.name}`")
        st.progress(feitas / n if n else 0.0, text=f"{feitas} de {n} anotadas")
        ir = st.number_input("Ir para o item nº", 1, n, i + 1)
        c1, c2 = st.columns(2)
        if c1.button("Ir"):
            st.session_state.i = int(ir) - 1
            st.rerun()
        if c2.button("Próximo pendente"):
            st.session_state.i = _indice_inicial(linhas)
            st.rerun()
        st.divider()
        st.markdown(
            "**Lembretes do codebook**\n\n"
            "- Compare sempre com o **gold**, não com as citações [D1].\n"
            "- Afirma algo falso como verdade? É erro. Só deixa de dizer? É lacuna.\n"
            "- Português e completude independem de a resposta estar certa.\n"
            "- Na dúvida, registre na observação."
        )

    # ---- item
    st.markdown(f"### Item {aid}  ·  {i + 1} de {n}  ·  {r['tipo']}"
                + ("  ·  **sem resposta no corpus**" if sem else ""))
    st.markdown(f"#### {r['pergunta']}")

    col_gold, col_resp = st.columns(2)
    with col_gold:
        st.markdown("##### O que é verdade (gold)")
        if r.get("gold_nota"):
            st.info(_destacar(r["gold_nota"]))
        if r.get("gold_evidencia"):
            for parte in r["gold_evidencia"].split(" || "):
                st.markdown("> " + _destacar(parte))
        if not r.get("gold_nota") and not r.get("gold_evidencia"):
            st.caption("Sem evidência gold registrada para esta pergunta.")
    with col_resp:
        st.markdown("##### O que o modelo respondeu")
        st.markdown(_destacar(r["resposta_gerada"]))

    st.divider()

    # ---- perguntas
    def radio(chave, bloco, valor_salvo):
        ops = list(bloco["opcoes"].keys())
        idx = ops.index(valor_salvo) if valor_salvo in ops else None
        return st.radio(bloco["pergunta"], ops, index=idx, key=f"{chave}_{aid}",
                        format_func=lambda k: bloco["opcoes"][k])

    def int_ou_none(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    q1, q2 = st.columns(2)
    with q1:
        st.markdown("**1. Suporte semântico**")
        acerto = radio("acerto", rb.pergunta_acerto(r["tem_resposta_no_corpus"]), dec.get("acerto"))
        erro = radio("erro", rb.ERRO, dec.get("erro"))
        sobra = radio("sobra", rb.SOBRA, dec.get("sobra")) if erro == "principal" else None
        d = rb.derivar(r["tem_resposta_no_corpus"], acerto, erro, sobra)
        if d.aviso:
            st.warning(d.aviso)
        else:
            st.success(f"Suporte semântico derivado: **{d.suporte}**"
                       + (f"  ·  recusa correta: **{d.recusa}**" if sem else ""))
        ajustar = st.checkbox("A nota derivada não reflete meu julgamento",
                              value=dec.get("ajuste_manual") == "sim", key=f"aj_{aid}")
        nota_final, just = d.suporte, ""
        if ajustar:
            nota_final = st.selectbox("Nota que eu atribuo", [1, 2, 3, 4], key=f"nf_{aid}",
                                      index=[1, 2, 3, 4].index(int_ou_none(dec.get("suporte_final")) or 3))
            just = st.text_input("Por quê? (obrigatório)", value=dec.get("justificativa_ajuste", ""),
                                 key=f"js_{aid}")
    with q2:
        st.markdown("**2. Português formal**")
        pt = radio("pt", rb.PT_FORMAL, int_ou_none(r.get("pt_formal")))
        st.markdown("**3. Completude**")
        comp = radio("comp", rb.COMPLETUDE, int_ou_none(r.get("completude")))
        obs = st.text_area("Observação (opcional)", value=r.get("observacao", ""), key=f"obs_{aid}")

    # ---- salvar / navegar
    pode_salvar = (nota_final is not None and pt is not None and comp is not None
                   and (not ajustar or just.strip()))
    b1, b2, b3 = st.columns([1, 1, 3])
    if b1.button("← Anterior", disabled=i == 0):
        st.session_state.i = i - 1
        st.rerun()
    if b2.button("Salvar e próximo →", type="primary", disabled=not pode_salvar):
        r["suporte_semantico"] = str(nota_final)
        r["pt_formal"] = str(pt)
        r["completude"] = str(comp)
        r["observacao"] = obs.strip()
        r["recusa_correta"] = d.recusa if sem else "n/a"
        linhas[i] = r
        rb.salvar_planilha(arquivo, campos, linhas, term)
        decisoes[aid] = {
            "anotacao_id": aid, "acerto": acerto, "erro": erro, "sobra": sobra or "",
            "suporte_derivado": d.suporte if d.suporte is not None else "",
            "suporte_final": nota_final, "ajuste_manual": "sim" if ajustar else "nao",
            "justificativa_ajuste": just.strip(),
            "salvo_em": datetime.now().isoformat(timespec="seconds"),
        }
        rb.salvar_decisoes(arquivo, decisoes)
        st.session_state.i = min(i + 1, n - 1)
        st.rerun()
    if not pode_salvar:
        b3.caption("Responda às perguntas (e justifique se ajustou a nota) para salvar.")
    elif rb.anotada(r):
        b3.caption("Item já anotado. Salvar de novo substitui as notas.")


if __name__ == "__main__":
    main()
