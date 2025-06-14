import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from agente_gemini import configurar_agente
from grafico_levantamento import gerar_grafico_por_data_interativo_com_media
from extrair_discursos import extrair_discursos_senado
import logging

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Cache para dados do Senado
@st.cache_data
def carregar_dados_senado(data_inicio, data_fim):
    return extrair_discursos_senado(data_inicio, data_fim)

# Cache para respostas do Gemini
@st.cache_data
def consultar_gemini(contexto, pergunta, data_inicio, data_fim, model_name):
    agente = configurar_agente(model_name=model_name)
    prompt = (
        f"Com base nos seguintes discursos do Senado (período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}):\n"
        f"{contexto}\n"
        f"Pergunta do usuário: {pergunta}\n"
        "Forneça uma resposta detalhada e, se aplicável, um resumo dos principais pontos dos discursos."
    )
    try:
        resposta = agente.generate_content(prompt)
        return resposta.text
    except Exception as e:
        if "429" in str(e):
            return (
                f"Erro: Limite de quota do Gemini API excedido ou modelo sem cota gratuita. "
                f"Verifique seu plano em https://ai.google.dev/gemini-api/docs/rate-limits. "
                f"Considere usar 'gemini-1.5-flash' ou ativar faturamento. Detalhes: {e}"
            )
        raise e

# Inicializa o estado da sessão
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()
if 'data_inicio' not in st.session_state:
    st.session_state.data_inicio = datetime(2025, 3, 1)
if 'data_fim' not in st.session_state:
    st.session_state.data_fim = datetime(2025, 3, 29)

st.set_page_config(page_title="Análise de Discursos com IA", layout="wide")
st.title("📊 Análise de Discursos do Senado com Agente Gemini")

# Seleção de período pelo usuário
st.subheader("📅 Selecione o Período de Análise (máximo 30 dias)")
col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data de Início", value=st.session_state.data_inicio, key="data_inicio_input")
with col2:
    data_fim = st.date_input("Data de Fim", value=st.session_state.data_fim, key="data_fim_input")

# Atualiza o estado da sessão com as datas selecionadas
st.session_state.data_inicio = data_inicio
st.session_state.data_fim = data_fim

# Valida o intervalo de 30 dias
if (data_fim - data_inicio).days > 30:
    st.error("O intervalo entre as datas não pode exceder 30 dias. Por favor, ajuste as datas.")
elif st.button("Carregar Discursos", key="carregar_discursos"):
    st.info(f"Carregando discursos de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}...")
    try:
        st.session_state.df = carregar_dados_senado(data_inicio, data_fim)
        if st.session_state.df.empty:
            st.warning("Nenhum discurso encontrado para o período selecionado.")
        else:
            st.success(f"Carregados {len(st.session_state.df)} discursos com sucesso!")
    except Exception as e:
        st.error(f"Erro ao carregar dados do Senado: {e}")
        st.session_state.df = pd.DataFrame()

# Exibe tabela e gráfico se o DataFrame não estiver vazio
if not st.session_state.df.empty:
    st.subheader("📋 Dados dos Discursos")
    st.dataframe(st.session_state.df[['DataSessao', 'CodigoPronunciamento',  'Resumo', 'TemaPrevisto', 'UrlTexto']], use_container_width=True)


    st.subheader("📈 Gráfico Interativo")
    try:
        fig = gerar_grafico_por_data_interativo_com_media(st.session_state.df)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Erro ao gerar gráfico: {e}")

# Interação com o agente Gemini
st.subheader("💬 Converse com o Agente sobre os Discursos")
model_options = ['gemini-2.0-flash', 'gemini-1.5-flash']
selected_model = st.selectbox("Selecione o modelo Gemini:", model_options, index=0, key="model_select")
pergunta = st.text_input("Digite sua pergunta sobre os discursos:", key="pergunta_input")

if pergunta and not st.session_state.df.empty:
    with st.spinner("Consultando o agente Gemini..."):
        try:
            # Limita o contexto para economizar tokens
            contexto = st.session_state.df[['DataSessao', 'CodigoPronunciamento', 'TipoDiscurso', 'TextoCompleto']].head(3).copy()
            contexto['TextoCompleto'] = contexto['TextoCompleto'].str[:500]  # Trunca para 500 caracteres
            contexto = contexto.to_dict('records')
            
            resposta = consultar_gemini(contexto, pergunta, st.session_state.data_inicio, st.session_state.data_fim, selected_model)
            st.markdown("**Resposta do Agente:**")
            st.write(resposta)
        except Exception as e:
            st.error(f"Erro ao consultar o Gemini: {e}")
elif pergunta and st.session_state.df.empty:
    st.warning("Carregue os discursos primeiro para fazer uma pergunta.")