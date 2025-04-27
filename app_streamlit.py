import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import threading
from legislativo_gpt import buscar_discursos, salvar_em_csv, salvar_em_pdf

# Configuração da página
st.set_page_config(page_title="Classificador de Discursos", layout="wide")
st.title("🗣️ Classificação de Discursos do Senado")

# Inicializar estados
if "executando" not in st.session_state:
    st.session_state.executando = False
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = None
if "discursos" not in st.session_state:
    st.session_state.discursos = None

# Entrada de datas
col1, col2 = st.columns(2)
with col1:
    data_inicio = st.date_input("Data de início", format="YYYY-MM-DD", value=datetime.today() - timedelta(days=7))
with col2:
    data_fim = st.date_input("Data de fim", format="YYYY-MM-DD", value=datetime.today())

intervalo = (data_fim - data_inicio).days
mensagem_erro = st.empty()

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

    progress_bar.empty()
    return discursos, time.time() - start_time

# Layout de botões
col1, col2 = st.columns([4, 1])
with col1:
    buscar = st.button("🔍 Buscar e Classificar Discursos", disabled=st.session_state.executando or intervalo > 30)
with col2:
    cancelar = st.button("❌ Cancelar Busca", disabled=not st.session_state.executando)

# Cancelar
if cancelar and st.session_state.executando:
    if st.session_state.stop_flag:
        st.session_state.stop_flag.set()
    st.session_state.executando = False
    st.warning("❌ Busca cancelada pelo usuário.")
    time.sleep(1)

# Buscar
if buscar and intervalo <= 30:
    st.session_state.executando = True

    with st.spinner("Buscando discursos... Isso pode levar alguns segundos..."):
        discursos, tempo_total = executar_busca()

    st.session_state.executando = False
    if discursos:
        st.success(f"✅ {len(discursos)} discursos encontrados em {tempo_total:.2f} segundos.")
        st.session_state.discursos = discursos
    else:
        st.warning("⚠️ Nenhum discurso encontrado ou busca cancelada.")

# Só continua se tivermos discursos
if st.session_state.discursos:

    df_discursos = pd.DataFrame(st.session_state.discursos)
    df_discursos.fillna("-", inplace=True)

    # 🔥 Filtros
    st.subheader("🔎 Filtros de Pesquisa")
    autores = sorted(df_discursos['NomeAutor'].unique())
    partidos = sorted(df_discursos['Partido'].unique())
    temas = sorted(df_discursos['Tema'].unique())

    filtro_autor = st.multiselect("Filtrar por Autor", autores, key="filtro_autor")
    filtro_partido = st.multiselect("Filtrar por Partido", partidos, key="filtro_partido")
    filtro_tema = st.multiselect("Filtrar por Tema", temas, key="filtro_tema")

    # Aplicar filtros
    df_filtrado = df_discursos.copy()

    if filtro_autor:
        df_filtrado = df_filtrado[df_filtrado['NomeAutor'].isin(filtro_autor)]
    if filtro_partido:
        df_filtrado = df_filtrado[df_filtrado['Partido'].isin(filtro_partido)]
    if filtro_tema:
        df_filtrado = df_filtrado[df_filtrado['Tema'].isin(filtro_tema)]

    discursos_filtrados = df_filtrado.to_dict(orient="records")

    # 🔥 Agrupamento
    st.subheader("📚 Agrupar Discursos")
    agrupamento = st.selectbox("Agrupar por:", ["Nenhum", "Partido", "Tema"])

    if agrupamento == "Nenhum":
        grupos = {"Todos os Discursos": discursos_filtrados}
    else:
        grupos = {}
        for discurso in discursos_filtrados:
            chave = discurso[agrupamento] or "Desconhecido"
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(discurso)

    # 🔥 Mostrar discursos agrupados
    for grupo, lista_discursos in grupos.items():
        st.markdown(f"### 📌 {grupo} ({len(lista_discursos)} discursos)")
        for discurso in lista_discursos:
            with st.expander(f"{discurso['NomeAutor']} ({discurso['Partido']}) - Tema: {discurso['Tema']}"):
                st.markdown(f"**Resumo:** {discurso['Resumo']}")
                st.markdown(f"**Texto Integral:** {discurso['TextoIntegral']}")

    # 🔥 Botões de Download
    salvar_em_csv(discursos_filtrados, nome_arquivo="discursos.csv")
    salvar_em_pdf(discursos_filtrados, nome_arquivo="relatorio_discursos.pdf")

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
