import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import threading
from legislativo_gpt import buscar_discursos, salvar_em_csv, salvar_em_pdf
from grafico_levantamento import gerar_grafico_por_data_interativo_com_media
import os
os.environ["STREAMLIT_SERVER_HEADLESS"] = "1"
os.environ["STREAMLIT_WATCHFILE_WATCHER_TYPE"] = "none"


# Configuração da página
st.set_page_config(
    page_title="Classificador de Discursos do Senado",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS melhorado
# CSS personalizado (apenas para elementos que não podem ser configurados via config.toml)
st.markdown("""
<style>
.stButton>button {
    width: 100%;
    border-radius: 10px;
    height: 3em;
    font-weight: 500;
}
.search-btn>button {
    background-color: #4CAF50;
    color: white;
}
.cancel-btn>button {
    background-color: #f44336;
    color: white;
}
.card-container {
    background-color: rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
}
.small-text {
    font-size: 0.8em;
    opacity: 0.8;
}
</style>
""", unsafe_allow_html=True)

# Cabeçalho com informações contextuais
st.title("🗣️ Classificação de Discursos do Senado")
with st.expander("ℹ️ Sobre esta ferramenta", expanded=False):
    st.markdown("""
    Esta ferramenta permite buscar, analisar e classificar discursos do Senado Federal brasileiro.
    
    **Como usar:**
    1. Selecione o intervalo de datas (máximo 30 dias)
    2. Clique em "Buscar e Classificar Discursos"
    3. Use os filtros para refinar sua pesquisa
    4. Explore os discursos e baixe os resultados em CSV ou PDF
    
    A visualização gráfica facilita a análise da quantidade de discursos por data.
    """)

# Inicializar estados
if "executando" not in st.session_state:
    st.session_state.executando = False
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = threading.Event()
if "discursos" not in st.session_state:
    st.session_state.discursos = None
if "pesquisa_texto" not in st.session_state:
    st.session_state.pesquisa_texto = ""

# Container para os controles de busca
with st.container():
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    
    # Layout de datas e busca mais compacto e organizado
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        st.subheader("📅 Período")
        data_inicio = st.date_input("Data de Início", format="YYYY-MM-DD")
    
    with col2:
        st.subheader("&nbsp;")  # Espaço para alinhar com a coluna anterior
        data_fim = st.date_input("Data de Fim", format="YYYY-MM-DD")
    
    with col3:
        st.markdown('<h3 style="margin-bottom: 10px;">💡 Dica Rápida</h3>', unsafe_allow_html=True)
        st.markdown("""
        <p style="font-size: 16px;">
        ➡️ Selecione um período de até <strong>30 dias</strong><br>
        ➡️ Refine a busca com <strong>filtros avançados</strong><br>
        ➡️ Explore e <strong>baixe</strong> os discursos
        </p>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


    
    # Verifica intervalo de datas
    intervalo = (data_fim - data_inicio).days
    mensagem_erro = st.empty()
    
    if intervalo > 30:
        mensagem_erro.error("⚠️ O intervalo de datas não pode ser maior que 30 dias.")
    elif intervalo < 0:
        mensagem_erro.error("⚠️ A data final deve ser posterior à data inicial.")
    else:
        mensagem_erro.empty()
    
    # Botões de ação em layout mais atrativo
    col_btn1, col_btn2 = st.columns([1, 1])
    
    with col_btn1:
        st.markdown('<div class="search-btn">', unsafe_allow_html=True)
        buscar = st.button("🔍 Buscar e Classificar Discursos", 
                          disabled=st.session_state.executando or intervalo > 30 or intervalo < 0)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_btn2:
        st.markdown('<div class="cancel-btn">', unsafe_allow_html=True)
        cancelar = st.button("❌ Cancelar Busca", 
                            disabled=not st.session_state.executando)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<p class="small-text">*Selecione um período de até 30 dias para obter resultados mais precisos.</p>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Função de execução
def executar_busca(data_inicio, data_fim):
    start_time = time.time()
    st.session_state.stop_flag.clear()
    
    # Container para status da busca
    status_container = st.container()
    with status_container:
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        st.subheader("Estado da Busca")
        progress_bar = st.progress(0)
        status_text = st.empty()
        status_text.info("Iniciando busca de discursos...")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Função de callback para atualizar o progresso
    def update_progress(progress):
        progress_bar.progress(progress)
    
    discursos = []
    try:
        # Passa a função de callback em vez da barra de progresso diretamente
        discursos = buscar_discursos(
            data_inicio.strftime("%Y%m%d"), 
            data_fim.strftime("%Y%m%d"), 
            stop_event=st.session_state.stop_flag, 
            _update_progress=update_progress  # Passa a função callback
        )
        if discursos:
            status_text.success(f"✅ Encontrados {len(discursos)} discursos!")
        else:
            status_text.warning("⚠️ Nenhum discurso encontrado.")
    except Exception as e:
        status_text.error(f"Erro durante a busca: {e}")
    
    time.sleep(1)
    status_container.empty()
    return discursos, time.time() - start_time

# Função para cancelar
def cancelar_busca():
    if st.session_state.executando:
        st.session_state.stop_flag.set()
        st.session_state.executando = False
        st.warning("❌ Busca cancelada pelo usuário.")
        time.sleep(1)

if cancelar:
    cancelar_busca()

if buscar and intervalo <= 30 and intervalo >= 0:
    st.session_state.executando = True
    
    with st.spinner("Buscando discursos... Isso pode levar alguns segundos..."):
        discursos, tempo_total = executar_busca(data_inicio, data_fim)
    
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
    
    # Exibir métricas gerais
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("📊 Visão Geral")
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Total de Discursos", len(df_discursos))
    with col_m2:
        st.metric("Senadores", df_discursos['NomeAutor'].nunique())
    with col_m3:
        st.metric("Partidos", df_discursos['Partido'].nunique())
    with col_m4:
        st.metric("Temas", df_discursos['Tema'].nunique())
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Filtros em layout de abas
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("🔎 Refinamento da Pesquisa")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📝 Por Texto", "👤 Por Autor/Partido", "🏷️ Por Tema", "📅 Por Data"])
    
    with tab1:
        texto_busca = st.text_input("Buscar nos discursos:", 
                                  value=st.session_state.pesquisa_texto,
                                  placeholder="Digite palavras-chave para filtrar os resultados")
    
    with tab2:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            autores = sorted(df_discursos['NomeAutor'].unique())
            filtro_autor = st.multiselect("Filtrar por Autor", autores, key="filtro_autor")
        
        with col_f2:
            partidos = sorted(df_discursos['Partido'].unique())
            filtro_partido = st.multiselect("Filtrar por Partido", partidos, key="filtro_partido")
    
    with tab3:
        temas = sorted(df_discursos['Tema'].unique())
        filtro_tema = st.multiselect("Filtrar por Tema", temas, key="filtro_tema")
        
        # Top temas para seleção rápida
        if temas:
            st.write("Selecionar tema rápido:")
            tema_counts = df_discursos['Tema'].value_counts().head(5)
            top_temas_cols = st.columns(len(tema_counts))
            for i, (tema, count) in enumerate(tema_counts.items()):
                if tema != "-":
                    with top_temas_cols[i]:
                        if st.button(f"{tema} ({count})", key=f"tema_rapido_{i}"):
                            filtro_tema = [tema]
    
    with tab4:
        col_dt1, col_dt2 = st.columns(2)
        with col_dt1:
            filtro_data_inicio = st.date_input("Data Inicial (filtro)", value=data_inicio)
        with col_dt2:
            filtro_data_fim = st.date_input("Data Final (filtro)", value=data_fim)
    
    # Modo de visualização
    modo_visualizacao = st.radio(
        "Modo de visualização:",
        options=["Resumo", "Detalhado", "Compacto"],
        horizontal=True
    )
    
    # Aplicar filtros
    df_filtrado = df_discursos.copy()
    
    # Filtro de texto
    if texto_busca:
        mask = (
            df_filtrado['TextoIntegral'].str.contains(texto_busca, case=False, na=False) |
            df_filtrado['Resumo'].str.contains(texto_busca, case=False, na=False) |
            df_filtrado['NomeAutor'].str.contains(texto_busca, case=False, na=False) |
            df_filtrado['Tema'].str.contains(texto_busca, case=False, na=False)
        )
        df_filtrado = df_filtrado[mask]
    
    # Outros filtros
    if filtro_autor:
        df_filtrado = df_filtrado[df_filtrado['NomeAutor'].isin(filtro_autor)]
    if filtro_partido:
        df_filtrado = df_filtrado[df_filtrado['Partido'].isin(filtro_partido)]
    if filtro_tema:
        df_filtrado = df_filtrado[df_filtrado['Tema'].isin(filtro_tema)]
    
    # Filtro de data
    df_filtrado['DataSessao'] = pd.to_datetime(df_filtrado['DataSessao'])
    df_filtrado = df_filtrado[
        (df_filtrado['DataSessao'].dt.date >= filtro_data_inicio) &
        (df_filtrado['DataSessao'].dt.date <= filtro_data_fim)
    ]
    
    discursos_filtrados = df_filtrado.to_dict(orient="records")
    
    # Mostrar número de resultados após filtro
    st.write(f"📝 **{len(discursos_filtrados)}** discursos correspondem aos filtros aplicados")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 🔥 Gerar e Exibir Gráfico Interativo
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("📊 Gráfico de Discursos por Data")
    if not df_filtrado.empty:
        grafico = gerar_grafico_por_data_interativo_com_media(df_filtrado)
        st.plotly_chart(grafico, use_container_width=True)
    else:
        st.info("Sem dados para exibir o gráfico. Ajuste os filtros.")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 🔥 Agrupamento
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("📚 Resultados")
    
    col_g1, col_g2 = st.columns([3, 1])
    with col_g1:
        agrupamento = st.selectbox(
            "Agrupar por:", 
            ["Nenhum", "Partido", "Tema", "Data", "Autor"],
            index=0
        )
    
    with col_g2:
        ordem = st.selectbox(
            "Ordenar por:",
            ["Data (mais recente)", "Data (mais antigo)", "Relevância"],
            index=0
        )
    
    # Ordenar discursos
    if ordem == "Data (mais recente)":
        discursos_filtrados = sorted(discursos_filtrados, key=lambda x: x.get('DataSessao', ''), reverse=True)
    elif ordem == "Data (mais antigo)":
        discursos_filtrados = sorted(discursos_filtrados, key=lambda x: x.get('DataSessao', ''))
    # Para "Relevância", mantemos a ordem original que presumivelmente já está ordenada por relevância
    
    # Agrupar discursos
    if agrupamento == "Nenhum":
        grupos = {"Todos os Discursos": discursos_filtrados}
    elif agrupamento == "Data":
        grupos = {}
        for discurso in discursos_filtrados:
            data = discurso.get('DataSessao', 'Desconhecido')
            if isinstance(data, pd.Timestamp):
                chave = data.strftime('%d/%m/%Y')
            else:
                chave = str(data).split(' ')[0] if ' ' in str(data) else str(data)
            
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(discurso)
        # Ordenar as chaves de data
        grupos = dict(sorted(grupos.items(), reverse=(ordem == "Data (mais recente)")))
    else:
        grupos = {}
        for discurso in discursos_filtrados:
            chave = discurso.get(agrupamento, "Desconhecido") or "Desconhecido"
            if chave not in grupos:
                grupos[chave] = []
            grupos[chave].append(discurso)
        # Ordenar por quantidade de discursos
        if ordem == "Relevância":
            grupos = dict(sorted(grupos.items(), key=lambda x: len(x[1]), reverse=True))
    
    # 🔥 Mostrar discursos agrupados
    for grupo, lista_discursos in grupos.items():
        st.markdown(f"### 📌 {grupo} ({len(lista_discursos)} discursos)")
        
        # Exibição depende do modo de visualização
        if modo_visualizacao == "Compacto":
            for i, discurso in enumerate(lista_discursos):
                if i % 3 == 0:
                    cols = st.columns(3)
                with cols[i % 3]:
                    st.markdown(f"""
                    **{discurso['NomeAutor']}** ({discurso['Partido']})  
                    *{discurso['DataSessao']}*  
                    Tema: {discurso['Tema']}
                    """)
                    with st.expander("Ver detalhes"):
                        st.markdown(f"**Resumo:** {discurso['Resumo']}")
                        if st.button(f"Ver texto completo", key=f"btn_{discurso['NomeAutor']}_{discurso['DataSessao']}_{id(discurso)}"):
                            st.markdown(f"**Texto Integral:**\n{discurso['TextoIntegral']}")
        
        elif modo_visualizacao == "Resumo":
            for discurso in lista_discursos:
                with st.expander(f"{discurso['DataSessao']}: {discurso['NomeAutor']} ({discurso['Partido']}) - Tema: {discurso['Tema']}"):
                    st.markdown(f"**Resumo:** {discurso['Resumo']}")
                    if st.button(f"Ver texto completo", key=f"btn_{discurso['NomeAutor']}_{discurso['DataSessao']}"):
                        st.markdown(f"**Texto Integral:**\n{discurso['TextoIntegral']}")
        
        else:  # Detalhado
            for discurso in lista_discursos:
                with st.expander(f"{discurso['DataSessao']}: {discurso['NomeAutor']} ({discurso['Partido']}) - Tema: {discurso['Tema']}"):
                    st.markdown(f"**Resumo:** {discurso['Resumo']}")
                    st.markdown(f"**Texto Integral:**\n{discurso['TextoIntegral']}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # 🔥 Botões de Download
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.subheader("📥 Exportar Resultados")
    
    # Preparar arquivos para download
    salvar_em_csv(discursos_filtrados, nome_arquivo="discursos.csv")
    salvar_em_pdf(discursos_filtrados, nome_arquivo="relatorio_discursos.pdf")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        with open("discursos.csv", "rb") as csv_file:
            st.download_button(
                label="📥 Baixar CSV dos Discursos",
                data=csv_file,
                file_name="discursos.csv",
                mime="text/csv",
                help="Baixe os discursos em formato CSV para análise em Excel ou outras ferramentas"
            )
    
    with col_d2:
        with open("relatorio_discursos.pdf", "rb") as pdf_file:
            st.download_button(
                label="📄 Baixar PDF dos Discursos",
                data=pdf_file,
                file_name="relatorio_discursos.pdf",
                mime="application/pdf",
                help="Baixe um relatório formatado em PDF com todos os discursos filtrados"
            )
    
    st.markdown('</div>', unsafe_allow_html=True)
else:
    # Exibir mensagem de boas-vindas quando não há discursos
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.info("""
    👋 **Bem-vindo ao Classificador de Discursos do Senado!**
    
    Para começar, selecione um intervalo de datas (até 30 dias) e clique no botão "Buscar e Classificar Discursos".
    
    Esta ferramenta permite:
    - Analisar discursos por tema, partido ou senador
    - Visualizar gráficos de distribuição temporal
    - Exportar os resultados em CSV ou PDF
    - Buscar por palavras-chave específicas
    """)
    st.markdown('</div>', unsafe_allow_html=True)