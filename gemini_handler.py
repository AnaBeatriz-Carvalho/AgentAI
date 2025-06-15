import streamlit as st
import google.generativeai as genai
import pandas as pd

def responder_pergunta_usuario(dataframe_classificado: pd.DataFrame, pergunta: str):
    """
    Usa o Gemini para responder a uma pergunta do usuário com base no DataFrame.
    """
    st.session_state.messages.append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)

    #
    model = genai.GenerativeModel('gemini-2.0-flash')
    

    contexto_dados = dataframe_classificado.to_markdown(index=False)

    prompt_qa = f"""
    Você é um assistente parlamentar e cientista de dados. Sua tarefa é analisar os dados de discursos do Senado brasileiro, que já foram extraídos e classificados por tema, e responder à pergunta do usuário.
    Seja preciso, objetivo e baseie-se SOMENTE nos dados fornecidos.

    **DADOS PARA ANÁLISE:**
    ---
    {contexto_dados[:20000]} # Envia um contexto substancial para análise
    ---

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