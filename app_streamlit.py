import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pathlib import Path
from data_processing import extrair_e_classificar_discursos
from gemini_handler import responder_pergunta_usuario


st.set_page_config(
    layout="wide", 
    page_title="Análise de Discursos do Senado com Agente Gemini",
    initial_sidebar_state="expanded"
)

dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Chave da API do Google não encontrada!")
    st.info("Por favor, verifique se o arquivo .env está na raiz do projeto e contém a variável GOOGLE_API_KEY.")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

st.title("🏛️ Análise dos Discursos do Senado com Agente Gemini")
st.markdown("Uma ferramenta para explorar, classificar e consultar os discursos do Senado Federal brasileiro.")

with st.sidebar:
    st.header("Filtros")
    data_fim_padrao = datetime.today()
    data_inicio_padrao = data_fim_padrao - timedelta(days=29)
    
    data_inicio = st.date_input("Data de Início", value=data_inicio_padrao, max_value=datetime.today())
    data_fim = st.date_input("Data de Fim", value=data_fim_padrao, max_value=datetime.today())

    if st.button("Buscar e Analisar Discursos", type="primary"):
      
        if 'messages' in st.session_state:
            del st.session_state.messages
        if 'df_discursos' in st.session_state:
            del st.session_state.df_discursos
        
        with st.spinner("Extraindo e analisando dados... Este processo pode levar alguns minutos."):
            st.session_state.df_discursos = extrair_e_classificar_discursos(data_inicio, data_fim)

if 'df_discursos' not in st.session_state or st.session_state.df_discursos.empty:
    st.info("Por favor, selecione um período na barra lateral e clique em 'Buscar e Analisar Discursos' para começar.")
    st.stop()

df = st.session_state.df_discursos


st.header("Dashboard Analítico")
col1, col2 = st.columns(2)

with col1:
    st.subheader("Frequência dos Temas")
    tema_counts = df['Tema'].value_counts().reset_index()
    tema_counts.columns = ['Tema', 'Contagem']
    fig_temas = px.bar(tema_counts, x='Tema', y='Contagem', title='Distribuição de Discursos por Tema',
                       color='Tema', template='plotly_white')
    st.plotly_chart(fig_temas, use_container_width=True)

with col2:
    st.subheader("Volume de Discursos por Dia")
    discursos_por_dia = df.groupby(df['Data'].dt.date).size().reset_index(name='Contagem')
    fig_temporal = px.line(discursos_por_dia, x='Data', y='Contagem', title='Linha do Tempo de Discursos',
                           markers=True, template='plotly_white')
    st.plotly_chart(fig_temporal, use_container_width=True)


st.subheader("Discursos Coletados e Classificados")
st.dataframe(df)


st.header("💬 Converse com os Dados")
st.markdown("Faça uma pergunta em linguagem natural sobre os dados apresentados.")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "assistant", "content": "Olá! Em que posso ajudar com a análise destes discursos?"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ex: Qual o tema mais debatido? Quem mais discursou?"):
    responder_pergunta_usuario(df, prompt)
