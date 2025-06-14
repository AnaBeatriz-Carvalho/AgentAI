# data_processing.py

import pandas as pd
import requests
from datetime import timedelta
from tqdm import tqdm
import streamlit as st
import google.generativeai as genai
import xml.etree.ElementTree as ET

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
    
    # Usando o endpoint que retorna a estrutura XML completa que você encontrou.
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
        
        # Iterando em todos os nós <Pronunciamento> no documento
        for pronunciamento_node in xml_root.findall('.//Pronunciamento'):
            def get_text(element_name):
                found_element = pronunciamento_node.find(element_name)
                return found_element.text.strip() if found_element is not None and found_element.text is not None else ""

            # =======================================================================
            # LÓGICA DE EXTRAÇÃO CORRIGIDA COM BASE NO SEU XML
            # =======================================================================
            discurso_data = {
                'Data': get_text('Data'),
                'Parlamentar': get_text('NomeAutor'), # <-- CORRIGIDO
                'Partido': get_text('Partido'),     # <-- CORRIGIDO
                'UF': get_text('UF'),               # <-- CORRIGIDO
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
    Classifica os discursos em temas usando a API do Gemini.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:   
        st.error(f"Erro ao inicializar o modelo Gemini. Verifique sua API Key. Erro: {e}")
        return df

    temas_previstos = []
    
    progress_bar = st.progress(0, text="Classificando discursos com o Agente Gemini...")
    
    for i, resumo in enumerate(tqdm(df['Resumo'].fillna(""), desc="Classificando discursos")):
        if len(resumo.split()) < 15: # Pula resumos muito curtos
            temas_previstos.append("Outros")
        else:
            prompt = f"""
            Analise o resumo do discurso parlamentar abaixo e classifique-o em UMA das seguintes categorias:
            {', '.join(TEMAS_DEFINIDOS)}.

            Responda APENAS com o nome da categoria. Não adicione textos, explicações ou pontuação.

            Resumo: "{resumo[:3000]}"
            Categoria:
            """
            try:
                response = model.generate_content(prompt)
                tema = response.text.strip()
                if tema not in TEMAS_DEFINIDOS:
                    temas_previstos.append("Outros") # Segurança contra respostas inesperadas
                else:
                    temas_previstos.append(tema)
            except Exception:
                temas_previstos.append("Erro na Classificação")
        
        # Atualiza a barra de progresso do Streamlit
        progress_bar.progress((i + 1) / len(df), text=f"Classificando discursos com o Agente Gemini... ({i+1}/{len(df)})")

    df['Tema'] = temas_previstos
    progress_bar.empty() # Limpa a barra de progresso
    return df
