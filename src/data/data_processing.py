import pandas as pd
import requests
import time
import streamlit as st
import xml.etree.ElementTree as ET
from src.ai.local_llm_handler import classificar_tema_local

# Lista de temas definidos no nosso artigo para guiar o modelo
TEMAS_DEFINIDOS = [
    "Educação", "Saúde", "Economia", "Cultura", "Segurança", 
    "Meio Ambiente", "Direitos Humanos", "Infraestrutura", 
    "Política", "Relações Exteriores", "Trabalho", "Outros"
]

@st.cache_data(ttl=86400) # Cache de 24 horas para não reprocessar os mesmos dados
def extrair_e_classificar_discursos(
    data_inicio,
    data_fim,
    sleep_between_batches: float = 5.0,
    classificar: bool = True,
):
    """
    Função principal que extrai pronunciamentos da API do Senado e os classifica via LLM local.
    """
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
    """
    Classifica discursos usando LLM local (LM Studio). Processa um a um para reduzir carga.
    """
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

def extrair_discursos_senado(data_inicio, data_fim):
    """
    Extrai pronunciamentos do Senado para o período especificado, utilizando
    a estrutura de dados correta (<NomeAutor>, <Partido>, etc.) para extrair todos os campos.
    """
    if (data_fim - data_inicio).days > 30:
        st.warning("O período selecionado excede 30 dias. A API do Senado pode não retornar todos os dados. Recomenda-se um intervalo menor.")

    data_inicio_str = data_inicio.strftime('%Y%m%d')
    data_fim_str = data_fim.strftime('%Y%m%d')
    
    url = f"https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/{data_inicio_str}/{data_fim_str}"
    
    headers = {
        'Accept': 'application/xml',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
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
            return pd.DataFrame()

        df = pd.DataFrame(discursos_list)
        df.dropna(subset=['Resumo', 'Data'], inplace=True)
        df = df[df['Resumo'].str.strip() != '']
        
        if df.empty:
            st.warning("Nenhum pronunciamento válido encontrado após a limpeza dos dados.")
            return pd.DataFrame()
            
        df['Data'] = pd.to_datetime(df['Data'], format='%Y-%m-%d', errors='coerce')
        df.dropna(subset=['Data'], inplace=True)
        
        return df

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == 404:
            st.error("Erro 404: Nenhum pronunciamento encontrado na API do Senado para as datas selecionadas.")
            st.warning("Isso geralmente ocorre em fins de semana, feriados ou recesso parlamentar. Por favor, tente um período com dias úteis.")
        else:
            st.error(f"Falha ao buscar dados na API do Senado. Status: {err.response.status_code}")
            st.error(f"Detalhe do erro: {err.response.text}")
        return pd.DataFrame()
    except requests.exceptions.Timeout:
        st.error("Erro de Timeout: A API do Senado demorou muito para responder. Tente novamente mais tarde.")
        return pd.DataFrame()
    except ET.ParseError as err:
        st.error(f"Falha ao processar a resposta XML da API do Senado.")
        st.error(f"Detalhe do erro: {err}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        return pd.DataFrame()
