"""Aba "Câmaras Municipais": dados do SAPL de qualquer câmara que use o sistema.

Fica em módulo próprio para não mexer no fluxo das abas do Senado. Os filtros ficam
dentro da aba (e não na barra lateral, que já é usada por Discursos e Votações).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from src.ai.municipal_qa import gerar_resposta_municipal
from src.sapl.camaras import CAMARAS_SAPL, normalizar_url_base
from src.sapl.client import SaplErro
from src.sapl.servico import DadosCamara, carregar_camara

_OPCAO_OUTRA = "Outra câmara (informar endereço do SAPL)"
_CHAVE_MSGS = "messages_municipal"


@st.cache_data(ttl=3600, show_spinner=False)
def _carregar_camara_cache(url_base: str, data_inicio: date, data_fim: date) -> DadosCamara:
    return carregar_camara(url_base, data_inicio, data_fim)


def _nome_da_url(url_base: str) -> str:
    """``https://sapl.lagarto.se.leg.br`` → ``lagarto``, para quando a câmara não está na lista."""
    host = url_base.split("://", 1)[-1].split("/", 1)[0]
    partes = host.split(".")
    return partes[1].capitalize() if len(partes) > 2 and partes[0] == "sapl" else host


def _selecao_camara() -> tuple[str | None, str | None]:
    opcoes = list(CAMARAS_SAPL) + [_OPCAO_OUTRA]
    escolha = st.selectbox("Câmara Municipal", opcoes, key="sapl_camara")
    if escolha != _OPCAO_OUTRA:
        return escolha, CAMARAS_SAPL[escolha]
    url = st.text_input(
        "Endereço do SAPL da câmara",
        placeholder="ex.: sapl.suacidade.uf.leg.br",
        key="sapl_url_custom",
        help="A lista de câmaras com SAPL está no site do Interlegis (Órgãos atendidos).",
    )
    if not url:
        return None, None
    try:
        url_base = normalizar_url_base(url)
    except ValueError as e:
        st.error(str(e))
        return None, None
    return _nome_da_url(url_base), url_base


def _painel_materias(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("Nenhuma matéria no período.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Matérias apresentadas", len(df))
    c2.metric("Em tramitação", int(df["Em tramitação"].sum()))
    c3.metric("Autores distintos", df["Autores"].str.split(", ").explode().replace("", pd.NA).nunique())

    col1, col2 = st.columns(2)
    with col1:
        por_tipo = df["Tipo"].replace("", "Não informado").value_counts().sort_values().reset_index()
        por_tipo.columns = ["Tipo", "Quantidade"]
        fig = px.bar(por_tipo, y="Tipo", x="Quantidade", orientation="h", template="plotly_white",
                     title="Matérias por tipo")
        fig.update_layout(height=360, yaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        por_tema = df["Tema"].value_counts().sort_values().reset_index()
        por_tema.columns = ["Tema", "Quantidade"]
        fig = px.bar(por_tema, y="Tema", x="Quantidade", orientation="h", template="plotly_white",
                     title="Matérias por tema (classificação automática)")
        fig.update_layout(height=360, yaxis_title="", showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "O tema é atribuído automaticamente por palavras-chave na ementa, com as mesmas categorias "
        "usadas para o Senado. É uma aproximação e pode errar."
    )

    with st.expander("Filtrar matérias"):
        termo = st.text_input("Palavra-chave na ementa", key="sapl_f_termo",
                              placeholder="ex.: escola, pavimentação, saúde")
        autores = sorted(set(df["Autores"].str.split(", ").explode().replace("", pd.NA).dropna()))
        f_autor = st.multiselect("Autor", autores, key="sapl_f_autor")
        f_tipo = st.multiselect("Tipo", sorted(t for t in df["Tipo"].unique() if t), key="sapl_f_tipo")

    filtrado = df
    if termo:
        filtrado = filtrado[filtrado["Ementa"].str.contains(termo, case=False, na=False, regex=False)]
    if f_autor:
        filtrado = filtrado[filtrado["Autores"].apply(lambda s: any(a in s.split(", ") for a in f_autor))]
    if f_tipo:
        filtrado = filtrado[filtrado["Tipo"].isin(f_tipo)]

    st.write(f"{len(filtrado)} matérias")
    st.dataframe(
        filtrado.drop(columns=["id_materia"]),
        column_config={
            "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
            "Link": st.column_config.LinkColumn("No SAPL", display_text="abrir"),
            "Texto original": st.column_config.LinkColumn("Texto", display_text="PDF"),
            "Ementa": st.column_config.TextColumn("Ementa", width="large"),
        },
        use_container_width=True,
        hide_index=True,
    )
    st.download_button("Baixar CSV das matérias", filtrado.to_csv(index=False),
                       file_name="materias_municipais.csv", key="sapl_dl_materias")


def _painel_vereadores(df_ver: pd.DataFrame, df_mat: pd.DataFrame) -> None:
    if df_ver.empty:
        st.info("A lista de vereadores não está disponível para esta câmara.")
        return
    so_ativos = st.toggle("Mostrar só quem está em exercício", value=True, key="sapl_so_ativos")
    df = df_ver[df_ver["Em exercício"]] if so_ativos else df_ver

    # Quantas matérias cada vereador assinou no período carregado.
    contagem = df_mat["Autores"].str.split(", ").explode().value_counts() if not df_mat.empty else pd.Series(dtype=int)
    df = df.assign(**{"Matérias no período": df["Vereador"].map(contagem).fillna(0).astype(int)})

    st.dataframe(
        df.drop(columns=["id_parlamentar"]),
        column_config={
            "Foto": st.column_config.ImageColumn("Foto", width="small"),
            "Página": st.column_config.LinkColumn("No SAPL", display_text="abrir"),
        },
        column_order=["Foto", "Vereador", "Partido", "Matérias no período", "Profissão",
                      "E-mail institucional", "Em exercício", "Nome completo", "Página"],
        use_container_width=True,
        hide_index=True,
    )
    st.caption("Mostramos apenas contatos institucionais. Telefones e e-mails pessoais cadastrados no SAPL não são exibidos.")


def _painel_votacoes(df: pd.DataFrame, indisponiveis: bool = False) -> None:
    if indisponiveis:
        st.info("Não foi possível consultar as votações desta câmara agora. Tente carregar de novo mais tarde.")
        return
    if df.empty:
        st.info("Esta câmara não registrou votações no SAPL para o período.")
        return
    st.dataframe(
        df.drop(columns=["id_votacao", "id_materia"]),
        column_config={"Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")},
        use_container_width=True,
        hide_index=True,
    )
    st.caption("O SAPL desta câmara registra o placar agregado; o voto individual de cada vereador nem sempre é lançado.")


def _painel_chat(dados: DadosCamara, nome: str) -> None:
    if dados.materias.empty:
        st.info("Carregue um período com matérias para conversar sobre elas.")
        return
    st.caption("Pergunte em linguagem natural. As respostas citam as matérias usadas, com link para o SAPL.")
    if _CHAVE_MSGS not in st.session_state:
        st.session_state[_CHAVE_MSGS] = [
            {"role": "assistant", "content": f"Olá! O que você quer saber sobre a Câmara de {nome}?"}
        ]
    for msg in st.session_state[_CHAVE_MSGS]:
        st.chat_message(msg["role"]).write(msg["content"])

    pergunta = st.chat_input("Ex.: o que foi pedido para a área da saúde?", key="sapl_chat_input")
    if not pergunta:
        return
    st.session_state[_CHAVE_MSGS].append({"role": "user", "content": pergunta})
    st.chat_message("user").write(pergunta)
    try:
        with st.spinner("Buscando matérias relevantes e elaborando a resposta..."):
            resultado = gerar_resposta_municipal(dados.materias, nome, pergunta)
    except Exception:
        resposta = ("Não consegui gerar a resposta agora. Verifique se o modelo local está em "
                    "execução (LM Studio) e tente novamente.")
        st.session_state[_CHAVE_MSGS].append({"role": "assistant", "content": resposta})
        st.chat_message("assistant").write(resposta)
        return
    st.session_state[_CHAVE_MSGS].append({"role": "assistant", "content": resultado["resposta"]})
    with st.chat_message("assistant"):
        st.write(resultado["resposta"])
        fontes = resultado["fontes_usadas"]
        if not fontes.empty:
            with st.expander(f"📚 Fontes ({len(fontes)} matérias)"):
                st.dataframe(
                    fontes[resultado["colunas_fonte"]],
                    column_config={
                        "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                        "Link": st.column_config.LinkColumn("No SAPL", display_text="abrir"),
                    },
                    use_container_width=True,
                    hide_index=True,
                )


def render() -> None:
    st.header("Câmaras Municipais")
    with st.expander("ℹ️ De onde vêm estes dados?"):
        st.markdown(
            "Muitas câmaras municipais usam o **SAPL** (Sistema de Apoio ao Processo Legislativo), "
            "oferecido gratuitamente pelo Interlegis, do Senado Federal. Ele registra o que os "
            "vereadores apresentam (indicações, requerimentos, projetos de lei, moções), as sessões "
            "e, quando a câmara lança, as votações.\n\n"
            "Esta aba consulta a API pública do SAPL da câmara escolhida. Cada câmara preenche o "
            "sistema do seu jeito, então a quantidade de informação varia de uma cidade para outra."
        )

    col_a, col_b, col_c = st.columns([2, 1, 1])
    with col_a:
        nome, url_base = _selecao_camara()
    hoje = datetime.today().date()
    with col_b:
        inicio = st.date_input("De", value=hoje - timedelta(days=89), max_value=hoje, key="sapl_inicio")
    with col_c:
        fim = st.date_input("Até", value=hoje, max_value=hoje, key="sapl_fim")

    if fim < inicio:
        st.error("❌ A data final não pode ser anterior à inicial.")
        return

    if st.button("Carregar dados da câmara", type="primary", disabled=url_base is None, key="sapl_carregar"):
        try:
            with st.spinner("Consultando o SAPL da câmara... a primeira consulta pode levar alguns segundos."):
                st.session_state.dados_camara = _carregar_camara_cache(url_base, inicio, fim)
            st.session_state.nome_camara = nome
            st.session_state.pop(_CHAVE_MSGS, None)
        except SaplErro as e:
            st.session_state.pop("dados_camara", None)
            st.error(f"Não foi possível consultar o SAPL desta câmara. Detalhe: {e}")

    dados: DadosCamara | None = st.session_state.get("dados_camara")
    if dados is None:
        st.info("Escolha uma câmara e um período e clique em **Carregar dados da câmara**.")
        return

    nome_atual = st.session_state.get("nome_camara", "")
    st.subheader(f"Câmara Municipal de {nome_atual}")
    for aviso in dados.avisos:
        st.warning(aviso)

    t_mat, t_ver, t_vot, t_chat = st.tabs(["Matérias", "Vereadores", "Votações", "💬 Converse"])
    with t_mat:
        _painel_materias(dados.materias)
    with t_ver:
        _painel_vereadores(dados.vereadores, dados.materias)
    with t_vot:
        _painel_votacoes(dados.votacoes, dados.votacoes_indisponiveis)
    with t_chat:
        _painel_chat(dados, nome_atual)
