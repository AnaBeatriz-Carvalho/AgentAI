
import pandas as pd
import requests
from datetime import timedelta
from tqdm import tqdm
import streamlit as st
import google.generativeai as genai
import xml.etree.ElementTree as ET
import time
import random
import json

# Lista de temas definidos no nosso artigo para guiar o modelo
TEMAS_DEFINIDOS = [
    "Educação", "Saúde", "Economia", "Cultura", "Segurança", 
    "Meio Ambiente", "Direitos Humanos", "Infraestrutura", 
    "Política", "Relações Exteriores", "Trabalho", "Outros"
]

@st.cache_data(ttl=86400) # Cache de 24 horas para não reprocessar os mesmos dados
def extrair_e_classificar_discursos(data_inicio, data_fim):
    """
    Função principal que extrai pronunciamentos da API do Senado e os classifica usando Gemini.
    """
    df_final = extrair_discursos_senado(data_inicio, data_fim)
    if df_final.empty:
        return df_final
        
    df_classificado = classificar_tema_discursos_com_gemini(df_final)
    return df_classificado

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
    
    st.write(f"Buscando pronunciamentos de {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}...")
    st.caption(f"URL da API: `{url}`")

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


def classificar_tema_discursos_com_gemini(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classifica discursos em lote (batch) com uma pausa entre cada lote
    para evitar os limites de requisição da API (rate limiting).
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:   
        st.error(f"Erro ao inicializar o modelo Gemini. Verifique sua API Key. Erro: {e}")
        return df

    temas_previstos = []
    batch_size = 20 # Classifica 20 discursos por vez
    
    discursos_para_classificar = df['Resumo'].fillna("").tolist()

    progress_bar = st.progress(0, text="Classificando discursos em lotes com o Agente Gemini...")

    for i in range(0, len(discursos_para_classificar), batch_size):
        batch_resumos = discursos_para_classificar[i:i + batch_size]
        
        prompt_batch = "Analise cada um dos resumos de discurso abaixo, numerados de 0 a {}.\n".format(len(batch_resumos) - 1)
        prompt_batch += "Classifique cada um em UMA das seguintes categorias: {}.\n".format(', '.join(TEMAS_DEFINIDOS))
        prompt_batch += "Responda com uma lista de objetos JSON, onde cada objeto tem uma chave 'index' e uma chave 'tema'. Exemplo: [{'index': 0, 'tema': 'Saúde'}, {'index': 1, 'tema': 'Economia'}].\n\n"

        for j, resumo in enumerate(batch_resumos):
            prompt_batch += f"Discurso {j}: \"{resumo[:1000]}\"\n"

        try:
            response = model.generate_content(prompt_batch)
            response_text = response.text.strip().replace("```json", "").replace("```", "")
            
            resultados_batch = json.loads(response_text)
            
            temas_lote = [""] * len(batch_resumos)
            for item in resultados_batch:
                if 'index' in item and 'tema' in item and 0 <= item['index'] < len(temas_lote):
                    temas_lote[item['index']] = item['tema'] if item['tema'] in TEMAS_DEFINIDOS else "Outros"

            temas_previstos.extend(temas_lote)

        except Exception as e:
            st.error(f"Erro ao processar lote {i//batch_size + 1}: {e}")
            temas_previstos.extend(["Erro na Classificação"] * len(batch_resumos))

        progress_bar.progress(min((i + batch_size) / len(discursos_para_classificar), 1.0), text=f"Classificando lote {i//batch_size + 1}...")
        
        # Pausa estratégica para respeitar o limite de 15 RPM (1 requisição a cada 4s)
        time.sleep(4.1)

    df['Tema'] = temas_previstos
    progress_bar.empty()
    return df