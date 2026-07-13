import sys
from pathlib import Path

# --- PyTorch primeiro (Windows / WinError 1114) ---
# O `c10.dll` do torch usa TLS estático no seu DllMain. Quando o torch é importado
# tarde (import preguiçoso do embedder, disparado por um clique), o processo já
# carregou dezenas de outras DLLs (pandas, plotly, openai, faiss...) e os slots de
# TLS podem estar esgotados, fazendo o DllMain falhar com WinError 1114. Importar o
# torch aqui, antes de tudo, garante que ele reserve o slot enquanto ainda há espaço.
# É best-effort: se o torch não estiver instalado, o app segue e o RAG avisa depois.
try:
    import torch  # noqa: F401
except Exception:
    pass

# Ensure project root is on sys.path so `import src.*` works when Streamlit
# executes the script with a working directory inside `src/`.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from pathlib import Path

# helper imports kept minimal; removed unused upload helper per user preference

from src.data.data_processing import extrair_e_classificar_discursos
from src.ai.local_llm_handler import responder_pergunta_usuario_local, explicar_votacao_local, responder_pergunta_votacao_local
from src.data.votacoes_handler import obter_votacoes_periodo
from src.utils.rastreabilidade import TRACE_PADRAO, avaliar, avaliar_por_origem, carregar_registros
from src.rag import rag_chat, indexer
from src.rag.vectorstore import VectorStore
from src.config.settings import get_rag_config

st.set_page_config(
    layout="wide",
    page_title="Análise de Atividades do Senado",
    initial_sidebar_state="expanded"
)

st.title("\U0001F3DB️ Análise de Atividades do Senado com LLM Local")

tab_discursos, tab_votacoes, tab_rastreabilidade = st.tabs(
    ["Análise de Discursos", "Análise de Votações", "📊 Rastreabilidade"]
)

with tab_discursos:
    st.header("Análise de Pronunciamentos Parlamentares")
    with st.sidebar:
        st.header("Filtros para Discursos")
        discursos_data_fim_padrao = datetime.today()
        discursos_data_inicio_padrao = discursos_data_fim_padrao - timedelta(days=29)

        discursos_data_inicio = st.date_input("Data de Início (Discursos)", value=discursos_data_inicio_padrao, max_value=datetime.today(), key="discursos_inicio")
        discursos_data_fim = st.date_input("Data de Fim (Discursos)", value=discursos_data_fim_padrao, max_value=datetime.today(), key="discursos_fim")

        if discursos_data_fim < discursos_data_inicio:
            st.error("❌ Data de fim não pode ser anterior à data de início!")

        with st.expander("Configuração de IA (LLM local)"):
            sleep_between_batches = st.number_input("Pausa entre chamadas (segundos)", min_value=0.0, max_value=10.0, value=0.5, step=0.1)

        if st.button("Procurar e Analisar Discursos", type="primary"):
            if 'messages' in st.session_state: del st.session_state.messages
            if 'df_discursos' in st.session_state: del st.session_state.df_discursos

            with st.spinner("A extrair e analisar discursos... Este processo pode demorar alguns minutos."):
                st.session_state.df_discursos = extrair_e_classificar_discursos(
                    discursos_data_inicio,
                    discursos_data_fim,
                    sleep_between_batches=float(sleep_between_batches),
                )

    if 'df_discursos' in st.session_state and not st.session_state.df_discursos.empty:
        df_discursos = st.session_state.df_discursos

        st.subheader("Dashboard Analítico dos Discursos")
        col1, col2 = st.columns(2)
        with col1:
            st.write("##### Frequência dos Temas")
            tema_counts = df_discursos['Tema'].value_counts().reset_index()
            tema_counts.columns = ['Tema', 'Contagem']
            tema_counts = tema_counts.sort_values('Contagem', ascending=True)
            fig_temas = px.bar(tema_counts, y='Tema', x='Contagem', orientation='h', title='Distribuição de Discursos por Tema',
                                color='Contagem', color_continuous_scale='Blues', template='plotly_white')
            fig_temas.update_traces(textposition='auto', texttemplate='%{x}', hovertemplate='%{y}: <b>%{x}</b><extra></extra>')
            fig_temas.update_layout(showlegend=False, height=400, xaxis_title='Quantidade', yaxis_title='')
            st.plotly_chart(fig_temas, use_container_width=True)
        with col2:
            st.write("##### Volume de Discursos por Dia")
            discursos_por_dia = df_discursos.groupby(df_discursos['Data'].dt.date).size().reset_index(name='Contagem') if 'Data' in df_discursos.columns else pd.DataFrame()
            if not discursos_por_dia.empty:
                discursos_por_dia.rename(columns={0: 'Data'}, inplace=True)
                fig_temporal = px.line(discursos_por_dia, x='Data', y='Contagem', title='Linha do Tempo de Discursos',
                                      markers=True, template='plotly_white', line_shape='linear')
                fig_temporal.update_traces(line=dict(color='#1f77b4', width=3), marker=dict(size=8),
                                          hovertemplate='%{x}: <b>%{y}</b> discursos<extra></extra>')
                fig_temporal.update_layout(height=400, xaxis_title='Data', yaxis_title='Quantidade',
                                         hovermode='x unified', showlegend=False)
                fig_temporal.update_xaxes(tickformat="%d/%m", showgrid=True, gridwidth=1, gridcolor='LightGray')
                fig_temporal.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
                st.plotly_chart(fig_temporal, use_container_width=True)

        st.subheader("Discursos Recolhidos e Classificados")
        st.dataframe(
            df_discursos,
            column_config={"Data": st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY")},
            use_container_width=True,
        )

        st.header("\U0001F4AC Converse com os Dados dos Discursos")
        st.caption("Faça uma pergunta em linguagem natural. As respostas trazem as **fontes** dos discursos usados.")
        if "messages" not in st.session_state:
            st.session_state["messages"] = [{"role": "assistant", "content": "Olá! Em que posso ajudar com a análise destes discursos?"}]

        _rag_cfg = get_rag_config()

        # Histórico do chat.
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt := st.chat_input("Faça uma pergunta sobre os discursos..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)

            # Fluxo automático: sem o usuário escolher "modo". Tentamos sempre a melhor
            # resposta (busca semântica com fontes). Se os discursos ainda não foram
            # preparados, preparamos aqui — só na primeira vez. Se qualquer etapa do RAG
            # falhar (ex.: dependência indisponível), caímos para a resposta simples pela
            # amostra carregada, de forma transparente para o cidadão.
            usar_rag = True
            if not VectorStore.exists(_rag_cfg["index_path"], _rag_cfg["meta_path"]):
                try:
                    with st.spinner("Preparando os discursos para busca... (apenas nesta primeira vez, pode levar alguns minutos)"):
                        stats = indexer.indexar_discursos(df_discursos)
                    usar_rag = stats["chunks"] > 0
                except Exception:
                    usar_rag = False

            if usar_rag:
                try:
                    with st.spinner("Buscando trechos relevantes e elaborando a resposta..."):
                        resultado = rag_chat.responder(prompt)
                    resposta, fontes = resultado["resposta"], resultado["fontes"]
                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    with st.chat_message("assistant"):
                        st.write(resposta)
                        if fontes:
                            df_fontes = pd.DataFrame(fontes)
                            cols_fonte = [c for c in ["ref", "Parlamentar", "Partido", "Data", "Tema", "score", "trecho"]
                                          if c in df_fontes.columns]
                            with st.expander(f"📚 Fontes ({len(fontes)} trechos citados)"):
                                st.dataframe(df_fontes[cols_fonte], use_container_width=True, hide_index=True)
                except Exception:
                    usar_rag = False  # cai para a resposta simples abaixo

            if not usar_rag:
                responder_pergunta_usuario_local(df_discursos, prompt, escrever_pergunta=False)

        # Opções avançadas: reindexação manual (para quando novos discursos forem coletados).
        with st.expander("⚙️ Opções avançadas"):
            _indice_existe = VectorStore.exists(_rag_cfg["index_path"], _rag_cfg["meta_path"])
            st.caption(
                "Os discursos são preparados automaticamente na primeira pergunta. "
                "Use o botão abaixo apenas para **atualizar** a busca após coletar novos discursos."
            )
            if st.button("🔄 Atualizar busca com os discursos atuais"):
                with st.spinner("Atualizando... pode levar alguns minutos."):
                    stats = indexer.indexar_discursos(df_discursos)
                st.success(f"Pronto: {stats['discursos']} discursos → {stats['chunks']} trechos "
                           f"({stats['com_integral']} com texto integral).")
            st.caption("Índice pronto." if _indice_existe else "Ainda não preparado — será feito na primeira pergunta.")

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
                st.dataframe(df_filtrado_discursos, use_container_width=True)
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

        if votacoes_data_fim < votacoes_data_inicio:
            st.error("❌ Data de fim não pode ser anterior à data de início!")

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

            - **Matéria**: a proposta legislativa em pauta (tipo, número e ano);
            - **O que foi votado**: a descrição do ponto específico decidido na votação;
            - **Ementa**: um resumo do conteúdo da proposta;
            - **Autoria** e **Situação atual**: quem propôs e em que estágio a matéria está;
            - **Resultado**: se foi aprovada ou rejeitada, com o placar.

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

        ementa = detalhes_materia.get('ementa') or 'Não informada'
        descricao_votacao = detalhes_materia.get('descricao_votacao') or ''
        autores = detalhes_materia.get('autores') or ''
        tipo_documento = detalhes_materia.get('tipo_documento') or ''
        situacao_atual = detalhes_materia.get('situacao_atual') or ''
        url_documento = detalhes_materia.get('url_documento') or ''
        identificacao = detalhes_materia.get('identificacao') or ''
        codigo_materia = detalhes_materia.get('codigo_materia')
        tipo_votacao = detalhes_materia.get('tipo_votacao', 'Nominal')
        resultado = detalhes_materia.get('resultado', 'Não informado')

        if identificacao:
            if codigo_materia:
                link_materia = f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{codigo_materia}"
                st.markdown(f"\U0001F4C4 **Matéria:** [{identificacao}]({link_materia})"
                            + (f" — {tipo_documento}" if tipo_documento else ""))
            else:
                st.markdown(f"\U0001F4C4 **Matéria:** {identificacao}"
                            + (f" — {tipo_documento}" if tipo_documento else ""))

        if descricao_votacao:
            st.markdown(f"\U0001F5F3️ **O que foi votado:** {descricao_votacao}")
        if ementa and ementa != 'Não informada':
            st.markdown(f"\U0001F4CC **Ementa:** *{ementa}*")
        if autores:
            st.markdown(f"👥 **Autoria:** {autores}")
        if situacao_atual:
            st.markdown(f"📍 **Situação atual:** {situacao_atual}")
        st.markdown(f"✅ **Resultado da votação:** {resultado}")
        if url_documento:
            st.markdown(f"🔗 [Ver texto integral da matéria]({url_documento})")

        st.write("---")
        st.subheader("💡 O que significa esta votação?")
        with st.spinner("IA analisando a matéria..."):
            explicacao = explicar_votacao_local(
                descricao_selecionada,
                ementa,
                tipo_votacao,
                resultado,
                autores=autores,
                tipo_documento=tipo_documento,
                situacao_atual=situacao_atual,
                descricao_votacao=descricao_votacao,
            )
            st.info(explicacao)
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

            # Provide CSV download of filtered votes
            if not df_filtrado.empty:
                st.download_button("Baixar votos filtrados (CSV)", df_filtrado.to_csv(index=False), file_name="votos_filtrados.csv")

        with col_grafico:
            st.write("##### Resumo dos Votos (Filtrado)")
            if not df_filtrado.empty:
                votos_counts = df_filtrado['Voto'].value_counts().reset_index()
                votos_counts.columns = ['Voto', 'Total']
                fig_votos = px.pie(votos_counts, names='Voto', values='Total', title='Distribuição dos Votos', hole=0.3)
                st.plotly_chart(fig_votos, use_container_width=True)
            else:
                st.warning("Nenhum voto corresponde aos filtros selecionados.")

        # Allow export of the selected voting details as CSV
        if df_votos is not None and not df_votos.empty:
            with st.expander("Exportar dados da votação selecionada"):
                st.download_button("Baixar CSV da votação", df_votos.to_csv(index=False), file_name="votacao_detalhes.csv")

        st.header("💬 Perguntas sobre esta Votação")
        if "messages_votacoes" not in st.session_state:
            st.session_state["messages_votacoes"] = [{"role": "assistant", "content": "Faça perguntas sobre esta votação e os votos dos senadores!"}]

        for msg in st.session_state.messages_votacoes:
            st.chat_message(msg["role"]).write(msg["content"])

        if prompt_votacao := st.chat_input("Faça uma pergunta sobre esta votação..."):
            st.session_state.messages_votacoes.append({"role": "user", "content": prompt_votacao})
            st.chat_message("user").write(prompt_votacao)

            responder_pergunta_votacao_local(
                df_votos=df_votos,
                detalhes=detalhes_materia,
                descricao=descricao_selecionada,
                tipo_votacao=tipo_votacao,
                resultado=resultado,
                pergunta=prompt_votacao,
            )


with tab_rastreabilidade:
    st.header("📊 Rastreabilidade das respostas")
    st.caption(
        "Estas porcentagens medem **rastreabilidade** (se a resposta se apoia em fontes reais), "
        "não acurácia de classificação. São calculadas a partir de `logs/qa_trace.jsonl`, que "
        "recebe uma linha a cada pergunta feita nos chats de Discursos e Votações."
    )

    # O clique no botão já provoca o rerun do script, relendo o log atualizado.
    st.button("🔄 Atualizar")

    registros = carregar_registros(TRACE_PADRAO)

    if not registros:
        st.info(
            "Ainda não há consultas registradas. Faça perguntas nos chats de **Discursos** ou "
            "**Votações** para gerar métricas. (O chat precisa do LM Studio servindo o modelo em "
            "`localhost:1234/v1` para produzir respostas com citações.)"
        )
    else:
        def _mostrar_metricas(m: dict):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Consultas", m.get("total", 0))
            c2.metric("Cobertura de recuperação", f"{m.get('cobertura_recuperacao', 0):.1%}")
            c3.metric("Cobertura de citação", f"{m.get('cobertura_citacao', 0):.1%}")
            c4.metric("Precisão de citação", f"{m.get('precisao_citacao', 0):.1%}")

        st.subheader("Geral")
        _mostrar_metricas(avaliar(registros))

        st.subheader("Por origem")
        por_origem = avaliar_por_origem(registros)
        for origem in sorted(por_origem):
            st.markdown(f"**{origem.capitalize()}**")
            _mostrar_metricas(por_origem[origem])

        with st.expander("O que cada métrica significa"):
            st.markdown(
                "- **Cobertura de recuperação**: % de perguntas em que o sistema encontrou ao menos "
                "1 fonte para embasar a resposta.\n"
                "- **Cobertura de citação**: % de respostas que citaram ao menos um id de fonte válido "
                "(presente entre as fontes recuperadas daquela pergunta).\n"
                "- **Precisão de citação**: dos ids citados pelo modelo, % que corresponde a fontes "
                "reais (não inventadas)."
            )
