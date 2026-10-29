"""Perguntas e respostas sobre a produção legislativa de uma câmara municipal (SAPL).

Segue o mesmo contrato de rastreabilidade do chat do Senado: as matérias recuperadas
entram no prompt com um ref curto (M1, M2...), o modelo é instruído a citar só esses
refs, e cada consulta vai para ``logs/qa_trace_local.jsonl`` com ``origem="municipal"``. Assim
a aba de Rastreabilidade mede o chat municipal com as mesmas métricas.

Reaproveita a recuperação por palavra-chave e o registro de trace do handler do Senado
sem alterá-los.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from src.ai.local_llm_handler import (
    _CFG,
    _normalizar,
    _registrar_trace,
    _selecionar_fontes,
    client,
)
from src.config.constants import MAX_CHARS_CONTEXTO_PROMPT, MAX_FONTES_PROMPT

ORIGEM_TRACE = "municipal"

_COLUNAS_BUSCA = ["Ementa", "Autores", "Partido", "Tema", "Tipo", "Identificação"]
_COLUNAS_PROMPT = ["ref", "Identificação", "Data", "Autores", "Partido", "Tema", "Ementa"]
COLUNAS_FONTE_UI = ["ref", "Identificação", "Data", "Autores", "Partido", "Ementa", "Link"]

# Palavras que aparecem em quase toda pergunta municipal e só geram ruído na busca
# (casariam com "Câmara Municipal" em muitas ementas).
_RUIDO_PERGUNTA = re.compile(
    r"\b(vereador(a|es|as)?|camara|municipal|municipio|cidade|projeto(s)?|materia(s)?)\b"
)


def _limpar_pergunta(pergunta: str) -> str:
    return _RUIDO_PERGUNTA.sub(" ", _normalizar(pergunta))


def _resumo_estatistico(df: pd.DataFrame) -> str:
    partes = [f"Total de matérias: {len(df)}."]
    datas = df["Data"].dropna() if "Data" in df.columns else pd.Series(dtype="datetime64[ns]")
    if not datas.empty:
        partes.append(f"Período: {datas.min().date()} a {datas.max().date()}.")
    if "Tipo" in df.columns:
        vc = df["Tipo"].replace("", pd.NA).dropna().value_counts().head(6)
        if not vc.empty:
            partes.append("Por tipo: " + ", ".join(f"{k} ({v})" for k, v in vc.items()) + ".")
    if "Autores" in df.columns:
        autores = (
            df["Autores"].fillna("").str.split(", ").explode().replace("", pd.NA).dropna()
        )
        vc = autores.value_counts().head(7)
        if not vc.empty:
            partes.append("Autores mais frequentes: " + ", ".join(f"{k} ({v})" for k, v in vc.items()) + ".")
    if "Tema" in df.columns:
        vc = df["Tema"].value_counts().head(8)
        if not vc.empty:
            partes.append("Temas (classificação automática por palavras-chave): "
                          + ", ".join(f"{k}: {v}" for k, v in vc.items()) + ".")
    return " ".join(partes)


def montar_prompt_municipal(
    df_materias: pd.DataFrame,
    nome_camara: str,
    pergunta: str,
    extra_context: Optional[str] = None,
) -> tuple[str, pd.DataFrame, list[str], list[str]]:
    """Monta o prompt de QA municipal. Função pura (não chama o LLM).

    Retorna ``(prompt, fontes_usadas, ids_fontes, codigos_fontes)``; ``codigos_fontes``
    são os ids reais das matérias no SAPL, para auditoria no trace.
    """
    df = df_materias.copy()
    fontes = _selecionar_fontes(
        df, _limpar_pergunta(pergunta), limite=MAX_FONTES_PROMPT, colunas_busca=_COLUNAS_BUSCA
    ).copy().reset_index(drop=True)
    fontes["ref"] = [f"M{i + 1}" for i in range(len(fontes))]

    fontes_prompt = fontes.copy()
    if "Data" in fontes_prompt.columns:
        fontes_prompt["Data"] = pd.to_datetime(fontes_prompt["Data"], errors="coerce").dt.strftime("%d/%m/%Y")
    colunas = [c for c in _COLUNAS_PROMPT if c in fontes_prompt.columns]
    contexto = fontes_prompt[colunas].to_markdown(index=False) if not fontes_prompt.empty else "Nenhuma matéria disponível."

    prompt = f"""Você é um assistente que explica a atividade da Câmara Municipal de {nome_camara} para cidadãos.
Responda à pergunta com base nas matérias legislativas listadas abaixo (indicações, requerimentos,
projetos de lei, moções etc.), apresentadas pelos vereadores e registradas no sistema SAPL da câmara.

Estatísticas de todas as matérias carregadas (use para totais e rankings):
{_resumo_estatistico(df)}

{extra_context or ''}

Matérias recuperadas (cada linha tem um id 'ref' único):
---
{contexto[:MAX_CHARS_CONTEXTO_PROMPT]}
---

Pergunta do cidadão:
"{pergunta}"

Diretrizes de resposta:
- Português brasileiro, linguagem simples, 4 a 6 frases.
- Explique brevemente o tipo da matéria quando ajudar (ex.: indicação é um pedido do vereador ao Executivo, não uma lei).
- Para afirmações sobre matérias específicas, cite o 'ref' entre colchetes ao final da frase (ex.: [M2]).
- UM id por colchete: escreva [M1] [M3], nunca [M1, M3]. Use só refs da lista acima.
- Não invente matérias, votos, valores ou fatos externos. Se a lista não responde à pergunta, diga isso claramente.
- O tema é uma classificação automática e pode errar; não o trate como informação oficial.

Resposta:
"""
    ids = fontes["ref"].astype(str).tolist()
    codigos = fontes["id_materia"].astype(str).tolist() if "id_materia" in fontes.columns else []
    return prompt, fontes, ids, codigos


def gerar_resposta_municipal(
    df_materias: pd.DataFrame,
    nome_camara: str,
    pergunta: str,
    extra_context: Optional[str] = None,
) -> dict:
    """Gera a resposta com o LLM local e registra o trace. Sem dependência de Streamlit."""
    prompt, fontes, ids, codigos = montar_prompt_municipal(df_materias, nome_camara, pergunta, extra_context)
    response = client.chat.completions.create(
        model=_CFG["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    resposta = (response.choices[0].message.content or "").strip()
    _registrar_trace(pergunta, ids, resposta, origem=ORIGEM_TRACE, fontes_codigos=codigos)
    return {
        "resposta": resposta,
        "fontes_usadas": fontes,
        "colunas_fonte": [c for c in COLUNAS_FONTE_UI if c in fontes.columns],
        "ids_fontes": ids,
        "codigos_fontes": codigos,
    }
