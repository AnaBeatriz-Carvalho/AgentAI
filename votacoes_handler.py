import pandas as pd
import requests
import xml.etree.ElementTree as ET
import streamlit as st
from difflib import get_close_matches

HEADERS = {
    'Accept': 'application/xml',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

@st.cache_data(ttl=3600)
def obter_votacoes_periodo(data_inicio, data_fim):
    """
    Busca todas as votações de um período com enriquecimento de informações da matéria.
    """
    data_inicio_str = data_inicio.strftime('%Y%m%d')
    data_fim_str = data_fim.strftime('%Y%m%d')

    url_orientacoes = f"https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/{data_inicio_str}/{data_fim_str}"
    url_detalhes = "https://legis.senado.leg.br/dadosabertos/votacao"

    try:
        # Busca os detalhes das matérias
        response_detalhes = requests.get(url_detalhes, headers=HEADERS, timeout=30)
        response_detalhes.raise_for_status()
        detalhes_root = ET.fromstring(response_detalhes.text)

        mapa_materias_detalhadas = {}
        for votacao in detalhes_root.findall('.//Votacao'):
            try:
                tipo = votacao.find('siglaTipoMateria').text
                numero = votacao.find('numeroMateria').text
                ano = votacao.find('anoMateria').text
                ementa = votacao.find('ementaMateria').text or ''
                resultado = votacao.find('resultado').text or ''
                tipo_votacao = votacao.find('descricaoVotacao').text or ''

                chave = f"{tipo} {numero}/{ano}"
                mapa_materias_detalhadas[chave] = {
                    "ementa": ementa,
                    "resultado": resultado,
                    "tipo_votacao": tipo_votacao
                }
            except Exception:
                continue

        # Busca as votações no período
        response_orientacoes = requests.get(url_orientacoes, headers=HEADERS, timeout=30)
        response_orientacoes.raise_for_status()
        root_orientacoes = ET.fromstring(response_orientacoes.text)

        votacoes_processadas = {}

        for votacao_node in root_orientacoes.findall('.//votacoes'):
            descricao_materia = votacao_node.find('descricaoMateria').text or "Matéria Indisponível"
            data_sessao = votacao_node.find('dataInicioVotacao').text.split(' ')[0] if votacao_node.find('dataInicioVotacao') is not None else ""
            chave = descricao_materia.strip()

            # Match aproximado com o mapa de matérias detalhadas
            chaves_detalhadas = list(mapa_materias_detalhadas.keys())
            chave_proxima = get_close_matches(chave, chaves_detalhadas, n=1, cutoff=0.6)

            if chave_proxima:
                detalhes = mapa_materias_detalhadas.get(chave_proxima[0], {})
            else:
                detalhes = {}

            ementa = detalhes.get("ementa", "")
            resultado = detalhes.get("resultado", "")
            tipo_votacao = detalhes.get("tipo_votacao", "")

            descricao_completa = f"{descricao_materia} (Votação em {data_sessao})"

            votos_list = []
            for voto_parlamentar in votacao_node.findall('votosParlamentar'):
                votos_list.append({
                    'Parlamentar': voto_parlamentar.find('nomeParlamentar').text,
                    'Partido': voto_parlamentar.find('partido').text,
                    'UF': voto_parlamentar.find('uf').text,
                    'Voto': voto_parlamentar.find('voto').text
                })

            if votos_list:
                df_votos = pd.DataFrame(votos_list)
                votacoes_processadas[descricao_completa] = {
                    "df_votos": df_votos,
                    "detalhes": {
                        "ementa": ementa,
                        "resultado": resultado,
                        "tipo_votacao": tipo_votacao
                    }
                }

        return votacoes_processadas

    except requests.RequestException as e:
        st.error(f"Erro ao buscar dados de votações: {e}")
        return {}

    except ET.ParseError as e:
        st.error(f"Erro ao processar XML de votações: {e}")
        return {}
