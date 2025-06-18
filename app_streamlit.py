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
from votacoes_handler import obter_votacoes_periodo 


st.set_page_config(
    layout="wide", 
    page_title="Análise de Atividades do Senado com Agente Gemini",
    initial_sidebar_state="expanded"
)


dotenv_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=dotenv_path)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    st.error("Chave da API do Google não encontrada!")
    st.info("Por favor, verifique se o ficheiro .env está na raiz do projeto e contém a variável GOOGLE_API_KEY.")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

st.title("🏛️ Análise de Atividades do Senado com Agente Gemini")


tab_discursos, tab_votacoes = st.tabs(["Análise de Discursos", "Análise de Votações"])


with tab_discursos:
    st.header("Análise de Pronunciamentos Parlamentares")
    with st.sidebar:
        st.header("Filtros para Discursos")
        discursos_data_fim_padrao = datetime.today()
        discursos_data_inicio_padrao = discursos_data_fim_padrao - timedelta(days=29)
        
        discursos_data_inicio = st.date_input("Data de Início (Discursos)", value=discursos_data_inicio_padrao, max_value=datetime.today(), key="discursos_inicio")
        discursos_data_fim = st.date_input("Data de Fim (Discursos)", value=discursos_data_fim_padrao, max_value=datetime.today(), key="discursos_fim")

        if st.button("Procurar e Analisar Discursos", type="primary"):
            if 'messages' in st.session_state: del st.session_state.messages
            if 'df_discursos' in st.session_state: del st.session_state.df_discursos
            
            with st.spinner("A extrair e analisar discursos... Este processo pode demorar alguns minutos."):
                st.session_state.df_discursos = extrair_e_classificar_discursos(discursos_data_inicio, discursos_data_fim)

    if 'df_discursos' in st.session_state and not st.session_state.df_discursos.empty:
        df_discursos = st.session_state.df_discursos
        
        st.subheader("Dashboard Analítico dos Discursos")
        col1, col2 = st.columns(2)
        with col1:
            st.write("##### Frequência dos Temas")
            tema_counts = df_discursos['Tema'].value_counts().reset_index()
            tema_counts.columns = ['Tema', 'Contagem']
            fig_temas = px.bar(tema_counts, x='Tema', y='Contagem', title='Distribuição de Discursos por Tema', color='Tema', template='plotly_white')
            st.plotly_chart(fig_temas, use_container_width=True)
        with col2:
            st.write("##### Volume de Discursos por Dia")
            discursos_por_dia = df_discursos.groupby(df_discursos['Data'].dt.date).size().reset_index(name='Contagem')
            fig_temporal = px.line(discursos_por_dia, x='Data', y='Contagem', title='Linha do Tempo de Discursos', markers=True, template='plotly_white')
            fig_temporal.update_xaxes(tickformat="%d/%m/%Y")
            st.plotly_chart(fig_temporal, use_container_width=True)

        st.subheader("Discursos Recolhidos e Classificados")
        st.dataframe(df_discursos, column_config={"Data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY")}, use_container_width=True)

        st.header("💬 Converse com os Dados dos Discursos")
        if "messages" not in st.session_state: st.session_state["messages"] = [{"role": "assistant", "content": "Olá! Em que posso ajudar com a análise destes discursos?"}]
        for msg in st.session_state.messages: st.chat_message(msg["role"]).write(msg["content"])
        if prompt := st.chat_input("Faça uma pergunta sobre os discursos..."): responder_pergunta_usuario(df_discursos, prompt)

    else:
        st.info("Para começar a análise de discursos, selecione um período na barra lateral e clique no botão 'Procurar e Analisar Discursos'.")


with tab_votacoes:
    st.header("Análise de Votações do Plenário")
    with st.sidebar:
        st.header("Filtros para Votações")
        votacoes_data_fim_padrao = datetime.today()
        votacoes_data_inicio_padrao = votacoes_data_fim_padrao - timedelta(days=6)
        
        votacoes_data_inicio = st.date_input("Data de Início (Votações)", value=votacoes_data_inicio_padrao, max_value=datetime.today(), key="votacoes_inicio")
        votacoes_data_fim = st.date_input("Data de Fim (Votações)", value=votacoes_data_fim_padrao, max_value=datetime.today(), key="votacoes_fim")

        if st.button("Procurar Votações", key="procurar_votacoes"):
            with st.spinner("A procurar votações no período..."):
                st.session_state.dados_votacoes = obter_votacoes_periodo(votacoes_data_inicio, votacoes_data_fim)

    if 'dados_votacoes' not in st.session_state:
        st.info("Para começar a análise de votações, selecione um período na barra lateral e clique em 'Procurar Votações'.")
    elif not st.session_state.dados_votacoes:
        st.warning("Nenhuma votação foi encontrada para o período selecionado. Por favor, tente outras datas.")
    else:
        dados_votacoes = st.session_state.dados_votacoes
        
        descricao_selecionada = st.selectbox(
            "Selecione uma votação para ver os detalhes:",
            options=dados_votacoes.keys()
        )
        
        df_votos = dados_votacoes[descricao_selecionada]
        
        st.subheader(f"Detalhes da Votação")
        st.markdown(f"**Matéria:** *{descricao_selecionada}*")
        
        st.write("---")
        st.write("##### Filtros Adicionais")
        partidos = sorted(df_votos['Partido'].unique())
        parlamentares = sorted(df_votos['Parlamentar'].unique())

        partido_selecionado = st.multiselect("Filtrar por Partido:", options=partidos)
        parlamentar_selecionado = st.multiselect("Filtrar por Parlamentar:", options=parlamentares)

        df_filtrado = df_votos.copy()
        if partido_selecionado:
            df_filtrado = df_filtrado[df_filtrado['Partido'].isin(partido_selecionado)]
        if parlamentar_selecionado:
            df_filtrado = df_filtrado[df_filtrado['Parlamentar'].isin(parlamentar_selecionado)]

        col_tabela, col_grafico = st.columns([2, 1])
        
        with col_tabela:
            st.write("##### Votos por Parlamentar")
            st.dataframe(df_filtrado, use_container_width=True)
        
        with col_grafico:
            st.write("##### Resumo dos Votos (Filtrado)")
            if not df_filtrado.empty:
                votos_counts = df_filtrado['Voto'].value_counts().reset_index()
                votos_counts.columns = ['Voto', 'Total']
                fig_votos = px.pie(votos_counts, names='Voto', values='Total', title='Distribuição dos Votos', hole=.3)
                st.plotly_chart(fig_votos, use_container_width=True)
            else:
                st.warning("Nenhum voto corresponde aos filtros selecionados.")
