import pandas as pd
import requests
import time
import streamlit as st
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from src.ai.local_llm_handler import classificar_tema_local
from src.config.constants import (
    TEMAS_DEFINIDOS, SENADO_API_DISCURSOS, SENADO_HEADERS,
    REQUEST_TIMEOUT, MAX_PERIODO_DIAS, COL_DATA, COL_RESUMO
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

@st.cache_data(ttl=86400)
def extrair_e_classificar_discursos(
    data_inicio: date,
    data_fim: date,
    sleep_between_batches: float = 5.0,
    classificar: bool = True,
) -> pd.DataFrame:
    """Extrai pronunciamentos do Senado e os classifica via LLM local."""
    df_final = extrair_discursos_senado(data_inicio, data_fim)
    if df_final.empty:
        return df_final

    if not classificar:
        df_final['Tema'] = 'Não classificado'
        return df_final

    return classificar_tema_discursos_com_local_llm(
        df_final,
        sleep_between_batches=sleep_between_batches,
    )


def classificar_tema_discursos_com_local_llm(
    df: pd.DataFrame,
    sleep_between_batches: float = 0.5,
) -> pd.DataFrame:
    """Classifica discursos usando LLM local (LM Studio)."""
    discursos = df['Resumo'].fillna("").tolist()
    temas_previstos: list[str] = [None] * len(discursos)

    progress_bar = st.progress(0, text="Classificando discursos com LLM local...")
    total = len(discursos) or 1

    for i, resumo in enumerate(discursos):
        tema = classificar_tema_local(resumo, TEMAS_DEFINIDOS)
        temas_previstos[i] = tema if tema in TEMAS_DEFINIDOS else "Outros"
        progresso = (i + 1) / total
        progress_bar.progress(min(progresso, 1.0), text=f"Classificando discurso {i + 1}/{total}...")
        time.sleep(sleep_between_batches)

    df['Tema'] = [t if t else 'Outros' for t in temas_previstos]
    progress_bar.empty()
    return df


def extrair_discursos_senado(data_inicio: date, data_fim: date) -> pd.DataFrame:
    """Extrai pronunciamentos do Senado para o período especificado."""
    if (data_fim - data_inicio).days > MAX_PERIODO_DIAS:
        st.warning(f"O período selecionado excede {MAX_PERIODO_DIAS} dias. A API do Senado pode não retornar todos os dados. Recomenda-se um intervalo menor.")
        logger.warning(f"Period exceeds {MAX_PERIODO_DIAS} days: {data_inicio} to {data_fim}")

    data_inicio_str = data_inicio.strftime('%Y%m%d')
    data_fim_str = data_fim.strftime('%Y%m%d')

    url = f"{SENADO_API_DISCURSOS}/{data_inicio_str}/{data_fim_str}"

    try:
        logger.info(f"Fetching discursos from {data_inicio_str} to {data_fim_str}")
        response = requests.get(url, headers=SENADO_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        xml_root = ET.fromstring(response.text)
        discursos_list = []

        for pronunciamento_node in xml_root.findall('.//Pronunciamento'):
            def get_text(element_name):
                found_element = pronunciamento_node.find(element_name)
                return found_element.text.strip() if found_element is not None and found_element.text is not None else ""

            discurso_data = {
                'Data': get_text('Data'),
                'Parlamentar': get_text('NomeAutor'),
                'Partido': get_text('Partido'),
                'UF': get_text('UF'),
                'Resumo': get_text('Resumo')
            }
            discursos_list.append(discurso_data)

        if not discursos_list:
            st.warning("Nenhum pronunciamento encontrado para o período selecionado.")
            logger.info(f"No discursos found for period {data_inicio_str} to {data_fim_str}")
            return pd.DataFrame()

        df = pd.DataFrame(discursos_list)
        df.dropna(subset=['Resumo', 'Data'], inplace=True)
        df = df[df['Resumo'].str.strip() != '']

        if df.empty:
            st.warning("Nenhum pronunciamento válido encontrado após a limpeza dos dados.")
            logger.info(f"No valid discursos after cleaning for period {data_inicio_str} to {data_fim_str}")
            return pd.DataFrame()

        df['Data'] = pd.to_datetime(df['Data'], format='%Y-%m-%d', errors='coerce')
        df.dropna(subset=['Data'], inplace=True)

        logger.info(f"Successfully extracted {len(df)} discursos")
        return df

    except requests.exceptions.HTTPError as err:
        status_code = err.response.status_code
        logger.error(f"HTTP error {status_code} fetching discursos", exc_info=True)
        if status_code == 404:
            st.info("😴 Nenhum pronunciamento encontrado para este período.")
            st.caption("Isso pode acontecer em fins de semana, feriados ou recesso. Tente um intervalo com dias úteis.")
        elif status_code == 400:
            st.info("⚠️ Não foi possível processar as datas fornecidas.")
            st.caption("Verifique se o período está correto (data de início ≤ data de fim).")
        elif status_code >= 500:
            st.info("🔧 O serviço do Senado está temporariamente indisponível.")
            st.caption("Tente novamente em alguns instantes.")
        else:
            st.error(f"Falha ao buscar dados na API do Senado. Status: {err.response.status_code}")
            st.error(f"Detalhe do erro: {err.response.text}")
        return pd.DataFrame()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching discursos from {data_inicio_str} to {data_fim_str}")
        st.info("⏱️ A requisição demorou muito para responder.")
        st.caption("A conexão pode estar lenta. Tente novamente em alguns instantes.")
        return pd.DataFrame()
    except ET.ParseError:
        logger.error(f"XML parse error for discursos period {data_inicio_str} to {data_fim_str}", exc_info=True)
        st.info("⚠️ Houve um problema ao processar os dados recebidos.")
        st.caption("Tente novamente com um período diferente.")
        return pd.DataFrame()
    except Exception as e:
        logger.error(f"Unexpected error fetching discursos: {e}", exc_info=True)
        st.info("⚠️ Algo inesperado aconteceu. Tente novamente mais tarde.")
        return pd.DataFrame()
