import sys
from pathlib import Path

# Ensure project root is on sys.path so `import src.*` works when Streamlit
# executes the script with a working directory inside `src/`.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import plotly.express as px
import google.generativeai as genai
from datetime import datetime, timedelta
import os
from pathlib import Path
from io import BytesIO

# helper imports kept minimal; removed unused upload helper per user preference

from src.data.data_processing import extrair_e_classificar_discursos
from src.ai.gemini_handler import responder_pergunta_usuario
from src.data.votacoes_handler import obter_votacoes_periodo
from src.config.settings import get_google_api_key

st.set_page_config(
    layout="wide",
    page_title="Análise de Atividades do Senado com Agente Gemini",
    initial_sidebar_state="expanded"
)

GOOGLE_API_KEY = get_google_api_key()
if not GOOGLE_API_KEY:
    st.error("Chave da API do Google não encontrada!")
    st.info("Por favor, verifique se o ficheiro .env está na raiz do projeto e contém a variável GOOGLE_API_KEY.")
    st.stop()
genai.configure(api_key=GOOGLE_API_KEY)

st.title("\U0001F3DB️ Análise de Atividades do Senado com Agente Gemini")

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
            st.plotly_chart(fig_temas, width='stretch')
        with col2:
            st.write("##### Volume de Discursos por Dia")
            discursos_por_dia = df_discursos.groupby(df_discursos['Data'].dt.date).size().reset_index(name='Contagem') if 'Data' in df_discursos.columns else pd.DataFrame()
            if not discursos_por_dia.empty:
                # garantir que a coluna de data tenha nome apropriado para o gráfico
                discursos_por_dia.rename(columns={0: 'Data'}, inplace=True)
                fig_temporal = px.line(discursos_por_dia, x='Data', y='Contagem', title='Linha do Tempo de Discursos', markers=True, template='plotly_white')
                fig_temporal.update_xaxes(tickformat="%d/%m/%Y")
                st.plotly_chart(fig_temporal, width='stretch')

        st.subheader("Discursos Recolhidos e Classificados")
        st.dataframe(df_discursos, column_config={"Data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY")}, width='stretch')

        st.header("\U0001F4AC Converse com os Dados dos Discursos")
        if "messages" not in st.session_state:
            st.session_state["messages"] = [{"role": "assistant", "content": "Olá! Em que posso ajudar com a análise destes discursos?"}]

        # Simple chat interface: display past messages and provide an input field
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        # Input field for free questions (minimal chat, no uploads or example prompts)
        if prompt := st.chat_input("Faça uma pergunta sobre os discursos..."):
            responder_pergunta_usuario(df_discursos, prompt)

        # Advanced filters: keyword, parlamentar, partido
        with st.expander("Filtros avançados (aplicáveis à tabela)"):
            palavra_chave = st.text_input("Filtrar por palavra-chave no resumo", value="", placeholder="ex.: saúde, educação")
            parlamentar_filtro = st.multiselect("Filtrar por Parlamentar:", options=sorted(df_discursos['Parlamentar'].unique()), default=None)
            partido_filtro = st.multiselect("Filtrar por Partido:", options=sorted(df_discursos['Partido'].unique()), default=None)

            df_filtrado_discursos = df_discursos.copy()
            if palavra_chave:
                df_filtrado_discursos = df_filtrado_discursos[df_filtrado_discursos['Resumo'].str.contains(palavra_chave, case=False, na=False)]
            if parlamentar_filtro:
                df_filtrado_discursos = df_filtrado_discursos[df_filtrado_discursos['Parlamentar'].isin(parlamentar_filtro)]
            if partido_filtro:
                df_filtrado_discursos = df_filtrado_discursos[df_filtrado_discursos['Partido'].isin(partido_filtro)]

            st.write(f"{len(df_filtrado_discursos)} discursos após aplicar filtros")
            if not df_filtrado_discursos.empty:
                st.download_button("Baixar CSV dos discursos filtrados", df_filtrado_discursos.to_csv(index=False), file_name="discursos_filtrados.csv")
                st.dataframe(df_filtrado_discursos, width='stretch')
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

        st.markdown("### \U0001F5F3️ Análise de Votações do Plenário")

        with st.expander("ℹ️ O que são essas votações?"):
            st.markdown("""
            As **votações do Plenário do Senado Federal** são momentos decisivos em que os senadores deliberam sobre temas de interesse público, como projetos de lei, propostas de emenda à Constituição, medidas provisórias, entre outros.

            Esta seção permite que você explore votações ocorridas em um período específico, visualizando:

            - **Matéria**: o título da proposta legislativa em pauta;
            - **Ementa**: um resumo breve do conteúdo da proposta;
            - **Tipo de Votação**: como a votação foi conduzida (nominal, simbólica etc.);
            - **Resultado**: se a proposta foi aprovada, rejeitada ou retirada.

            Utilize os filtros à esquerda para buscar votações entre datas específicas e entenda como os parlamentares têm votado sobre diferentes assuntos.
            """)

        descricao_selecionada = st.selectbox(
            "Selecione uma votação para ver os detalhes:",
            options=list(dados_votacoes.keys())
        )

        dados_da_votacao_selecionada = dados_votacoes[descricao_selecionada]
        df_votos = dados_da_votacao_selecionada['df_votos']
        detalhes_materia = dados_da_votacao_selecionada['detalhes']

        st.subheader("Detalhes da Votação")
        codigo_materia = detalhes_materia.get('codigo_materia')
        if codigo_materia:
            link_materia = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigo_materia}"
            st.markdown(f"**Matéria:** *{descricao_selecionada}*  ")
            st.markdown(f"**Código da Matéria:** [{codigo_materia}]({link_materia})")
        else:
            st.markdown(f"**Matéria:** *{descricao_selecionada}*")

        ementa = detalhes_materia.get('ementa') or 'Não informada'
        explicacao = detalhes_materia.get('explicacao') or ''
        autores = detalhes_materia.get('autores') or ''
        tipo_votacao = detalhes_materia.get('tipo_votacao', 'Não informado')
        resultado = detalhes_materia.get('resultado', 'Não informado')

        if ementa and ementa != 'Não informada':
            st.markdown(f"\U0001F4CC **Ementa:** *{ementa}*")
        if explicacao:
            st.markdown(f"📝 **Explicação da Ementa:** {explicacao}")
        if autores:
            st.markdown(f"👥 **Autores:** {autores}")
        st.markdown(f"\U0001F5F3️ **Tipo de Votação:** {tipo_votacao}")
        st.markdown(f"✅ **Resultado:** {resultado}")

        # Botão para gerar explicação via IA
        from src.ai.gemini_handler import explicar_votacao
        with st.expander("💡 Gerar explicação automática desta votação"):
            if st.button("Gerar Explicação", key=f"explicar_{codigo_materia or descricao_selecionada}"):
                with st.spinner("Gerando explicação com IA..."):
                    explicacao_ia = explicar_votacao(detalhes_materia, df_votos, descricao_selecionada)
                st.markdown("**Explicação Gerada:**")
                st.write(explicacao_ia)

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
            st.dataframe(df_filtrado, width='stretch')

            # Provide CSV download of filtered votes
            if not df_filtrado.empty:
                st.download_button("Baixar votos filtrados (CSV)", df_filtrado.to_csv(index=False), file_name="votos_filtrados.csv")

        with col_grafico:
            st.write("##### Resumo dos Votos (Filtrado)")
            if not df_filtrado.empty:
                votos_counts = df_filtrado['Voto'].value_counts().reset_index()
                votos_counts.columns = ['Voto', 'Total']
                fig_votos = px.pie(votos_counts, names='Voto', values='Total', title='Distribuição dos Votos', hole=0.3)
                st.plotly_chart(fig_votos, width='stretch')
            else:
                st.warning("Nenhum voto corresponde aos filtros selecionados.")

        # Allow export of the selected voting details as CSV
        if df_votos is not None and not df_votos.empty:
            with st.expander("Exportar dados da votação selecionada"):
                st.download_button("Baixar CSV da votação", df_votos.to_csv(index=False), file_name="votacao_detalhes.csv")
