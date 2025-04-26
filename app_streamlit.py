import streamlit as st
import time
from datetime import datetime, timedelta
import threading
from legislativo_gpt import buscar_discursos

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

if intervalo > 30:
    mensagem_erro.error("⚠️ O intervalo de datas não pode ser maior que 30 dias.")
else:
    mensagem_erro.empty()

def executar_busca():
    start_time = time.time()

    # Thread simulada para tempo em tempo real
    stop_flag = threading.Event()

    def atualizar_tempo():
        while not stop_flag.is_set():
            tempo_execucao_box.markdown(
                f"⏱️ Tempo de execução: **{time.time() - start_time:.1f} segundos**"
            )
            time.sleep(0.5)

    t = threading.Thread(target=atualizar_tempo)
    t.start()

    discursos = buscar_discursos(data_inicio.strftime("%Y%m%d"), data_fim.strftime("%Y%m%d"))

    stop_flag.set()
    t.join()
    tempo_execucao_box.empty()
    return discursos, time.time() - start_time

if st.button("🔍 Buscar e Classificar Discursos") and intervalo <= 30:
    status_info.info("🔄 Buscando discursos... Isso pode levar alguns segundos.")
    discursos, tempo_total = executar_busca()

    status_info.empty()

    if discursos:
        st.success(f"✅ {len(discursos)} discursos encontrados em {tempo_total:.2f} segundos.")
        for discurso in discursos:
            with st.expander(f"{discurso['NomeAutor']} ({discurso['Partido']}) - Tema: {discurso['Tema']}"):
                st.markdown(f"**Resumo:** {discurso['Resumo']}")
                st.markdown(f"**Texto Integral:** {discurso['TextoIntegral']}")
                st.markdown(f"[🔗 Ver Documento]({discurso['UrlTextoBinario']})")
    else:
        st.warning("Nenhum discurso encontrado ou erro na consulta.")
