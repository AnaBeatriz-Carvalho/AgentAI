import streamlit as st
import google.generativeai as genai
import pandas as pd
from typing import Dict

def _get_model():
    """Retorna sempre o modelo gemini-2.0-flash (padronizado pelo usuário)."""
    return genai.GenerativeModel('gemini-2.0-flash')


def responder_pergunta_usuario(dataframe_classificado: pd.DataFrame, pergunta: str, extra_context: str = None):
    """
    Usa o Gemini para responder a uma pergunta do usuário com base no DataFrame.
    """
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    model = _get_model()
    
    contexto_dados = dataframe_classificado.to_markdown(index=False)

    prompt_qa = f"""
    Você é um assistente parlamentar e cientista de dados. Sua tarefa é analisar os dados de discursos do Senado brasileiro, que já foram extraídos e classificados por tema, e responder à pergunta do usuário.
    Seja preciso, objetivo e baseie-se SOMENTE nos dados fornecidos.

    **DADOS PARA ANÁLISE:**
    ---
    {contexto_dados[:20000]} # Envia um contexto substancial para análise
    ---

    {extra_context or ''}

    **PERGUNTA DO USUÁRIO:**
    "{pergunta}"
    ---

    **SUA RESPOSTA (em português brasileiro):**
    """
    
    with st.spinner("O Agente Gemini está analisando os dados e elaborando sua resposta..."):
        try:
            response = model.generate_content(prompt_qa)
            resposta = response.text
            st.session_state.messages.append({"role": "assistant", "content": resposta})
            st.chat_message("assistant").write(resposta)
        except Exception as e:
            st.error(f"Ocorreu um erro ao contatar o Gemini: {e}")


def explicar_votacao(detalhes: Dict, df_votos: pd.DataFrame) -> str:
    """Gera uma explicação em linguagem natural sobre a votação usando IA.

    Considera ementa, explicação, autores e distribuição de votos. Usa fallback de modelo.
    Cache simples por código da matéria para evitar custo repetido.
    """
    codigo = detalhes.get('codigo_materia') or detalhes.get('codigo') or ''
    cache_key = f"explic_votacao_{codigo}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    contagem_votos = df_votos['Voto'].value_counts().to_dict() if 'Voto' in df_votos.columns else {}
    resumo_votos = ', '.join([f"{k}: {v}" for k, v in contagem_votos.items()])
    autores = detalhes.get('autores', '')
    ementa = detalhes.get('ementa', '')
    explicacao = detalhes.get('explicacao', '')
    resultado = detalhes.get('resultado', '')
    tipo_votacao = detalhes.get('tipo_votacao', '')

    prompt = f"""
    Você é um analista legislativo. Produza uma explicação clara e objetiva sobre uma votação do Senado.
    Use somente os dados fornecidos, não invente conteúdo externo.

    DADOS DA VOTAÇÃO:
    Código: {codigo or 'Não disponível'}
    Tipo de Votação: {tipo_votacao or 'Não informado'}
    Resultado: {resultado or 'Não informado'}
    Ementa: {ementa or 'Sem ementa'}
    Explicação da Ementa: {explicacao or 'Sem explicação'}
    Autores: {autores or 'Não informados'}
    Distribuição dos Votos: {resumo_votos or 'Sem votos'}

    TAREFA:
    - Resuma o objeto da votação.
    - Contextualize brevemente o que significa o resultado.
    - Destaque, se pertinente, como a distribuição dos votos pode indicar consenso ou divisão.
    - Seja conciso (até ~180 palavras) e em português brasileiro.
    """

    model = _get_model()
    try:
        resposta = model.generate_content(prompt).text.strip()
    except Exception as e:
        resposta = f"Não foi possível gerar explicação automática (erro: {e})."

    st.session_state[cache_key] = resposta
    return resposta
