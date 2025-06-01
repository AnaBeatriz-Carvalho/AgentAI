import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging

# Configura logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extrair_discursos_senado(data_inicio, data_fim):
    """
    Extrai discursos do Senado para o período especificado e retorna como DataFrame.
    
    Args:
        data_inicio (datetime): Data de início do período.
        data_fim (datetime): Data de fim do período.
    
    Returns:
        pd.DataFrame: DataFrame com os discursos extraídos.
    
    Raises:
        ValueError: Se o intervalo de datas exceder 30 dias.
    """
    try:
        # Valida o intervalo de 30 dias
        if (data_fim - data_inicio).days > 30:
            raise ValueError("O intervalo entre as datas não pode exceder 30 dias.")

        # Formata as datas para o endpoint
        data_inicio_str = data_inicio.strftime('%Y%m%d')
        data_fim_str = data_fim.strftime('%Y%m%d')
        url = f"https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/{data_inicio_str}/{data_fim_str}"

        # Faz a requisição
        logging.info(f"Acessando API do Senado: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            logging.error(f"Erro ao acessar API do Senado: {response.status_code} - {response.text}")
            raise Exception(f"Erro ao acessar API do Senado: {response.status_code}")

        # Log da resposta
        logging.info(f"Resposta da API (primeiros 2000 caracteres): {response.text[:2000]}")

        # Parseia o XML
        try:
            root = ET.fromstring(response.content)
            logging.info("XML parseado com sucesso")
        except ET.ParseError as e:
            logging.error(f"Erro ao parsear XML: {e}")
            raise Exception(f"Erro ao parsear XML: {e}")

        discursos = []
        for pronunciamento in root.findall(".//Pronunciamento"):
            try:
                codigo = pronunciamento.findtext("CodigoPronunciamento") or ""
                data_sessao = pronunciamento.findtext("Data") or ""
                tipo_discurso = pronunciamento.findtext("TipoUsoPalavra/Descricao") or "Desconhecido"
                resumo = pronunciamento.findtext("Resumo") or ""
                url_texto = pronunciamento.findtext("TextoIntegralTxt") or pronunciamento.findtext("TextoIntegral") or ""

                # Tenta obter o texto completo
                texto_completo = resumo  # Fallback para o resumo
                if url_texto:
                    try:
                        texto_response = requests.get(url_texto, timeout=10)
                        if texto_response.status_code == 200:
                            texto_completo = texto_response.text
                            logging.info(f"Texto completo baixado: {url_texto}")
                        else:
                            logging.warning(f"Erro ao baixar texto: {url_texto} - Status {texto_response.status_code}")
                    except Exception as e:
                        logging.warning(f"Erro ao baixar texto {url_texto}: {e}")

                discursos.append({
                    "DataSessao": data_sessao,
                    "CodigoPronunciamento": codigo,
                    "TipoDiscurso": tipo_discurso,
                    "Resumo": resumo,
                    "TextoCompleto": texto_completo,
                    "UrlTexto": url_texto
                })
            except Exception as e:
                logging.warning(f"Erro ao processar pronunciamento: {e}")
                continue

        if not discursos:
            logging.warning("Nenhum pronunciamento encontrado no período especificado.")
            return pd.DataFrame()

        # Cria DataFrame
        df = pd.DataFrame(discursos)
        logging.info(f"Registros antes de dropna: {len(df)}")
        df['DataSessao'] = pd.to_datetime(df['DataSessao'], format='%Y-%m-%d', errors='coerce')
        df.dropna(subset=['DataSessao'], inplace=True)
        logging.info(f"Registros após dropna: {len(df)}")
        
        if df.empty:
            logging.warning("DataFrame vazio após processamento.")
        
        return df

    except Exception as e:
        logging.error(f"Erro na extração de discursos: {e}")
        return pd.DataFrame()