import streamlit as st
import time
from datetime import datetime, timedelta
import threading
import pandas as pd
from legislativo_gpt import buscar_discursos, salvar_em_csv, salvar_em_pdf

st.set_page_config(page_title="Classificador de Discursos", layout="wide")
st.title("🗣️ Classificação de Discursos do Senado")

# Entrada de datas
col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data de início", format="YYYY-MM-DD", value=datetime.today() - timedelta(days=7))
with col2:
    data_fim = st.date_input("Data de fim", format="YYYY-MM-DD", value=datetime.today())

intervalo = (data_fim - data_inicio).days
mensagem_erro = st.empty()
status_info = st.empty()
tempo_execucao_box = st.empty()
mensagem_cancelamento = st.empty()

if "executando" not in st.session_state:
    st.session_state.executando = False
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = None

if intervalo > 30:
    mensagem_erro.error("⚠️ O intervalo de datas não pode ser maior que 30 dias.")
else:
    mensagem_erro.empty()

# Função de execução
def executar_busca():
    start_time = time.time()
    st.session_state.stop_flag = threading.Event()
    st.session_state.stop_flag.clear()

    progress_bar = st.progress(0)

    discursos = []
    try:
        discursos = buscar_discursos(
            data_inicio.strftime("%Y%m%d"), 
            data_fim.strftime("%Y%m%d"), 
            stop_event=st.session_state.stop_flag, 
            update_progress=progress_bar
        )
    except Exception as e:
        st.error(f"Erro durante a busca: {e}")

    st.session_state.stop_flag.set()
    progress_bar.empty()
    return discursos, time.time() - start_time

# Layout de botões
col1, col2 = st.columns([4, 1])
with col1:
    buscar = st.button("🔍 Buscar e Classificar Discursos", disabled=st.session_state.executando or intervalo > 30)
with col2:
    cancelar = st.button("❌ Cancelar Busca", disabled=not st.session_state.executando)

# Cancelamento
if cancelar and st.session_state.executando:
    st.session_state.stop_flag.set()
    st.session_state.executando = False
    mensagem_cancelamento.warning("❌ Busca cancelada pelo usuário.")
    time.sleep(2)
    mensagem_cancelamento.empty()

# Execução
if buscar and intervalo <= 30:
    st.session_state.executando = True

    with st.spinner("Buscando discursos... Isso pode levar alguns segundos..."):
        discursos, tempo_total = executar_busca()

    st.session_state.executando = False
    status_info.empty()

    if st.session_state.stop_flag.is_set() and not discursos:
        st.warning("Busca cancelada antes de terminar.")
    elif discursos:
        st.success(f"✅ {len(discursos)} discursos encontrados em {tempo_total:.2f} segundos.")

        # Mostrar discursos
        for discurso in discursos:
            with st.expander(f"{discurso['NomeAutor']} ({discurso['Partido']}) - Tema: {discurso['Tema']}"):
                st.markdown(f"**Resumo:** {discurso['Resumo']}")
                st.markdown(f"**Texto Integral:** {discurso['TextoIntegral']}")
                st.markdown(f"[🔗 Ver Documento]({discurso['UrlTextoBinario']})")

        # Gerar CSV e PDF
        salvar_em_csv(discursos, nome_arquivo="discursos.csv")
        salvar_em_pdf(discursos, nome_arquivo="relatorio_discursos.pdf")

        with open("discursos.csv", "rb") as csv_file:
            st.download_button(
                label="📥 Baixar CSV dos Discursos",
                data=csv_file,
                file_name="discursos.csv",
                mime="text/csv"
            )

        with open("relatorio_discursos.pdf", "rb") as pdf_file:
            st.download_button(
                label="📄 Baixar PDF dos Discursos",
                data=pdf_file,
                file_name="relatorio_discursos.pdf",
                mime="application/pdf"
            )

    else:
        st.warning("Nenhum discurso encontrado ou erro na consulta.")
