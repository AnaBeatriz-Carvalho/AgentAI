import pandas as pd
import requests
import xml.etree.ElementTree as ET
import streamlit as st


HEADERS = {
    'Accept': 'application/xml',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

@st.cache_data(ttl=3600) 
def obter_votacoes_periodo(data_inicio, data_fim):
    """
    Busca todas as votações de um período usando o endpoint de Orientação de Bancada,
    que se provou o mais completo e confiável.
    """
    data_inicio_str = data_inicio.strftime('%Y%m%d')
    data_fim_str = data_fim.strftime('%Y%m%d')
    
    
    url = f"https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/{data_inicio_str}/{data_fim_str}"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        xml_root = ET.fromstring(response.text)
        
        votacoes_processadas = {}

       
        for votacao_node in xml_root.findall('.//votacoes'):
            
            
            descricao_materia = votacao_node.find('descricaoMateria').text if votacao_node.find('descricaoMateria') is not None else "Matéria Indisponível"
            data_sessao = votacao_node.find('dataInicioVotacao').text.split(' ')[0] if votacao_node.find('dataInicioVotacao') is not None else ""
            descricao_completa = f"{descricao_materia} (Votação em {data_sessao})"

            votos_list = []
            for voto_parlamentar in votacao_node.findall('votosParlamentar'):
                voto_data = {
                    'Parlamentar': voto_parlamentar.find('nomeParlamentar').text,
                    'Partido': voto_parlamentar.find('partido').text,
                    'UF': voto_parlamentar.find('uf').text,
                    'Voto': voto_parlamentar.find('voto').text
                }
                votos_list.append(voto_data)
            
            if votos_list:
                df_votos = pd.DataFrame(votos_list)
                votacoes_processadas[descricao_completa] = df_votos
        
        return votacoes_processadas

    except requests.exceptions.HTTPError as err:
      
        if err.response.status_code == 404:
            pass
        else:
            st.error(f"Falha ao buscar dados de votações. Status: {err.response.status_code}")
        return {}
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao processar votações: {e}")
        return {}
