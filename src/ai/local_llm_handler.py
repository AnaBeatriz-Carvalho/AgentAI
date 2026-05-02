from openai import OpenAI
import json
import re
import streamlit as st
import pandas as pd
from typing import Optional

from src.config.settings import get_local_llm_config

_CFG = get_local_llm_config()
client = OpenAI(base_url=_CFG["base_url"], api_key=_CFG["api_key"])


_ANALISE_SCHEMA_EXEMPLO = {
    "parlamentar": "",
    "partido": "",
    "estado": "",
    "agenda_politica": "",
    "tema_principal": "",
    "resumo": "",
    "posicionamento_governo": "",
    "tom_politico": "",
    "atores_mencionados": [],
}


def _extract_first_json_object(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return cleaned[start : end + 1]


def _default_insuficiente() -> dict:
    d = dict(_ANALISE_SCHEMA_EXEMPLO)
    d.update(
        {
            "parlamentar": "não identificado",
            "partido": "não identificado",
            "estado": "não identificado",
            "agenda_politica": "outros",
            "tema_principal": "não identificado",
            "resumo": "conteúdo insuficiente",
            "posicionamento_governo": "indeterminado",
            "tom_politico": "neutro",
            "atores_mencionados": [],
        }
    )
    return d


def _coerce_analise_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        return _default_insuficiente()
    out = dict(_default_insuficiente())
    for k in _ANALISE_SCHEMA_EXEMPLO.keys():
        if k in payload:
            out[k] = payload[k]

    # Normalizações leves
    if not isinstance(out.get("atores_mencionados"), list):
        out["atores_mencionados"] = []
    out["atores_mencionados"] = [str(x).strip() for x in out["atores_mencionados"] if str(x).strip()][:5]

    for k in ["parlamentar", "partido", "estado", "agenda_politica", "tema_principal", "resumo", "posicionamento_governo", "tom_politico"]:
        out[k] = (str(out.get(k, "")).strip() or "não identificado")

    # Regras
    if out["resumo"].lower() == "conteúdo insuficiente" or out["resumo"].lower() == "conteudo insuficiente":
        return _default_insuficiente()
    return out


def _build_prompt_analise_discurso(texto: str) -> str:
    return f"""
Você é um cientista político especializado em análise de discursos parlamentares brasileiros e análise de linguagem política.

Raciocine internamente para garantir consistência, mas NÃO mostre seu raciocínio.

Objetivos da análise:
- Identificar a agenda política do discurso usando uma categoria fixa.
- Identificar o tema principal do discurso.
- Produzir um resumo claro e objetivo.
- Identificar o posicionamento político em relação ao governo.
- Identificar o tom político do discurso.
- Extrair atores políticos ou institucionais mencionados.
- Identificar automaticamente o parlamentar, partido e estado se essas informações estiverem presentes no texto.

Categorias fixas de agenda política (escolha apenas 1):

economia - créditos, financiamentos, impostos, câmbio, PIB, mercado, investimentos, setor privado
saúde - SUS, medicamentos, hospitais, pandemia, vacinação, doenças, saúde pública
educação - escolas, universidades, ensino, pesquisa científica, bolsas de estudo
segurança pública - polícia, crime, violência, presídios, segurança pessoal
infraestrutura - rodovias, ferrovias, portos, aeroportos, água, saneamento, energia, telecomunicações
meio ambiente - desmatamento, poluição, mudanças climáticas, sustentabilidade, preservação
agricultura - produção agrícola, agropecuária, pecuária, fertilizantes, subsídios agrícolas
ciência e tecnologia - inovação, pesquisa, tecnologia, startups
direitos sociais - pobreza, desigualdade, programas sociais, seguro desemprego
política institucional - reforma política, poder judiciário, poder legislativo, constituição
relações internacionais - diplomacia, comércio exterior, acordos bilaterais, organismos internacionais
administração pública - reforma administrativa, funcionalismo público, orçamento
justiça e legislação - leis, regulamentações, direitos legais, processos judiciais
outros - não se encaixa nas categorias acima

Posicionamento em relação ao governo (escolha apenas 1):
apoio ao governo, oposição ao governo, posição institucional, neutro / informativo, indeterminado

Tom político (escolha apenas 1):
crítico, elogioso, defensivo, neutro

Regras obrigatórias:
- Não invente informações que não estejam no texto.
- Se alguma informação não puder ser identificada, retorne "não identificado".
- O resumo deve ter no máximo 2 frases.
- O tema principal deve ter no máximo 5 palavras e deve ser baseado no ASSUNTO PRINCIPAL, não em palavras-chave isoladas.
- Extraia no máximo 5 atores mencionados.
- Se o discurso for muito curto para análise adequada, retorne exatamente "conteúdo insuficiente" no campo "resumo".
- IMPORTANTE: Identifique o tema baseado no CONTEXTO E OBJETIVO PRINCIPAL do texto, não apenas em palavras isoladas.

Estrutura obrigatória da resposta:
- Responda EXCLUSIVAMENTE em JSON VÁLIDO (sem Markdown, sem texto extra).
- Use exatamente estas chaves:
{json.dumps(_ANALISE_SCHEMA_EXEMPLO, ensure_ascii=False)}

Discurso a ser analisado (texto bruto):
<<DISCURSO>>
{texto}
<<FIM>>
"""


def analisar_discurso_struct(texto: str) -> dict:
    """Analisa um discurso com o LLM local e retorna um dict (robusto a respostas fora do formato)."""
    if not texto or len(texto.strip()) < 40:
        return _default_insuficiente()

    prompt = _build_prompt_analise_discurso(texto)

    try:
        response = client.chat.completions.create(
            model=_CFG["model"],
            messages=[
                {"role": "system", "content": "Você responde apenas JSON válido, sem texto extra."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
    except Exception:
        return _default_insuficiente()

    raw = _extract_first_json_object(text)
    if not raw:
        return _default_insuficiente()

    try:
        payload = json.loads(raw)
    except Exception:
        return _default_insuficiente()

    return _coerce_analise_payload(payload)


def analisar_discurso(texto: str) -> str:
    """Compat: retorna a análise como string JSON."""
    return json.dumps(analisar_discurso_struct(texto), ensure_ascii=False)


def classificar_tema_local(resumo: str, temas: list[str]) -> str:
    """Classifica um resumo em um tema da lista usando palavras-chave."""
    palavras_chave = {
        "Educação": ["educação", "ensino", "escola", "universidade", "aluno", "professor", "bolsa", "pesquisa", "ciência", "tecnologia", "inovação", "acadêmico"],
        "Saúde": ["saúde", "sus", "medicamento", "hospital", "médico", "doença", "vacinação", "pandemia", "enfermidade", "clínico"],
        "Economia": ["economia", "crédito", "financiamento", "imposto", "câmbio", "pib", "investimento", "setor privado", "mercado", "inflação", "operação de crédito"],
        "Segurança": ["segurança pública", "polícia", "crime", "violência", "prisão", "criminalidade", "delegacia", "criminal"],
        "Infraestrutura": ["rodovia", "ferrovia", "porto", "aeroporto", "saneamento", "energia", "água", "construção", "obra", "resiliência", "manutenção"],
        "Meio Ambiente": ["meio ambiente", "desmatamento", "poluição", "climática", "sustentabilidade", "preservação", "ecologia", "floresta", "carbono"],
        "Direitos Humanos": ["direitos humanos", "direito", "liberdade", "igualdade", "dignidade", "minorias", "discriminação", "humano"],
        "Trabalho": ["trabalho", "emprego", "labor", "agricultura", "agropecuária", "produtor", "sindicato", "trabalhador", "rural"],
        "Política": ["política", "congresso", "senado", "câmara", "governo", "poder", "instituição", "legislação", "lei", "reforma", "parlamentar"],
        "Relações Exteriores": ["relações exteriores", "diplomacia", "internacional", "exterior", "país", "comércio exterior", "acordo", "embaixada"],
        "Cultura": ["cultura", "arte", "música", "cinema", "patrimônio", "cultural", "artista", "festival"],
    }

    texto_lower = resumo.lower()
    contagem = {}

    for tema, palavras in palavras_chave.items():
        contagem[tema] = sum(1 for palavra in palavras if palavra in texto_lower)

    tema_vencedor = max(contagem, key=contagem.get)

    if contagem[tema_vencedor] > 0:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info(f"Tema identificado: {tema_vencedor} (correspondências: {contagem[tema_vencedor]})")
        return tema_vencedor

    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Classificado como: Outros")
    return "Outros"


def explicar_votacao_local(descricao_materia: str, ementa: str, tipo_votacao: str, resultado: str) -> str:
    """Explica uma matéria de votação de forma clara e acessível."""
    prompt = f"""
Você é um especialista em legislação brasileira explicando para um cidadão leigo o que significa uma votação no Senado.

Matéria: {descricao_materia}
Ementa: {ementa}
Tipo de Votação: {tipo_votacao}
Resultado: {resultado}

Forneça uma explicação clara e concisa (3-4 frases) que inclua:
1. O que é esta matéria em linguagem simples
2. O que significa o tipo de votação utilizado
3. O resultado e sua importância

Seja objetivo e evite jargão técnico desnecessário.
"""

    try:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)

        response = client.chat.completions.create(
            model=_CFG["model"],
            messages=[
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        explicacao = response.choices[0].message.content.strip()
        logger.info(f"Explicação de votação gerada com sucesso")
        return explicacao
    except Exception as e:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Erro ao explicar votação: {str(e)}", exc_info=True)
        return "Desculpe, não consegui gerar uma explicação no momento. Tente novamente."


def responder_pergunta_usuario_local(dataframe_classificado: pd.DataFrame, pergunta: str, extra_context: Optional[str] = None):
    """Responde à pergunta do usuário usando o LLM local e o contexto dos discursos."""
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    df = dataframe_classificado.copy()

    # Estatísticas do período
    periodo_txt = ""
    if 'Data' in df.columns and not df['Data'].empty:
        datas_validas = df['Data'].dropna()
        if not datas_validas.empty:
            min_d = datas_validas.min().date()
            max_d = datas_validas.max().date()
            periodo_txt = f"Intervalo: {min_d} a {max_d} (registros: {len(datas_validas)})."

    # Parlamentares mais frequentes na amostra
    top_parlamentares_txt = ""
    if 'Parlamentar' in df.columns:
        vc_parl = df['Parlamentar'].value_counts()
        if not vc_parl.empty:
            top_parlamentares_txt = ", ".join([f"{nome} ({cont})" for nome, cont in vc_parl.head(7).items()])
            top_parlamentares_txt = f"Mais ativos (discursos): {top_parlamentares_txt}."

    # Distribuição de temas
    temas_dist_txt = ""
    if 'Tema' in df.columns:
        vc_tema = df['Tema'].value_counts()
        if not vc_tema.empty:
            temas_dist_txt = ", ".join([f"{tema}: {cont}" for tema, cont in vc_tema.head(10).items()])
            temas_dist_txt = f"Temas predominantes: {temas_dist_txt}."

    total_discursos = len(df)
    resumo_stats = f"Total: {total_discursos}. {periodo_txt} {top_parlamentares_txt} {temas_dist_txt}".strip()

    contexto_dados = df.to_markdown(index=False)

    prompt_qa = f"""Você é um assistente parlamentar e cientista de dados. Analise os discursos e responda à pergunta abaixo.
Gere insights RELATIVOS à amostra: frequências de parlamentares, predominância de temas, variações no período.
Se a pergunta exigir dado ausente (ex.: presença física), explique brevemente a limitação e ofereça alternativa
baseada em padrões de discursos e temas. Evite descartar totalmente a resposta; sempre traga ângulo útil.

Estatísticas resumidas:
{resumo_stats}

Pergunta do usuário:
"{pergunta}"

{extra_context or ''}

Dados tabulares (amostra):
---
{contexto_dados[:16000]}
---

Diretrizes de resposta:
- Português brasileiro, claro e conciso.
- 4–6 frases objetivas.
- Referencie parlamentares com mais discursos quando pertinente.
- Use temas para qualificar tendências.
- Indique se período é curto, mas ainda ofereça leitura relativa.
- Não repita a pergunta, não use jargões desnecessários.
- Não invente fatos externos.

Resposta:
"""

    with st.spinner("O LLM local está analisando os dados e elaborando sua resposta..."):
        try:
            from src.utils.logger import get_logger
            logger = get_logger(__name__)
            logger.info(f"Respondendo pergunta do usuário: {pergunta[:50]}...")

            response = client.chat.completions.create(
                model=_CFG["model"],
                messages=[
                    {"role": "user", "content": prompt_qa},
                ],
                temperature=0.2,
            )
            resposta = response.choices[0].message.content.strip()
            logger.info(f"Resposta gerada com sucesso: {resposta[:50]}...")
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)
        except Exception as e:
            from src.utils.logger import get_logger
            logger = get_logger(__name__)
            logger.error(f"Erro ao responder pergunta: {str(e)}", exc_info=True)
            resposta = "Desculpe, tive uma dificuldade momentânea em processar sua pergunta. Por favor, tente novamente em alguns instantes ou reformule a pergunta."
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)