import pandas as pd
import requests
import xml.etree.ElementTree as ET
import streamlit as st
from difflib import get_close_matches
import re
import json
from pathlib import Path

CACHE_PATH = Path('outputs/materias_cache.json')

HEADERS = {
    'Accept': 'application/xml',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
}

def obter_detalhes_materia(codigo_materia: str) -> dict:
    """Consulta detalhes adicionais de uma matéria legislativa.

    Retorna ementa, explicação da ementa e autores (lista concatenada) se disponíveis.
    """
    if not codigo_materia:
        return {}
    url = f"https://legis.senado.leg.br/dadosabertos/materia/{codigo_materia}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ementa = root.find('.//EmentaMateria')
        explicacao = root.find('.//ExplicacaoEmentaMateria')
        autores_nodes = root.findall('.//Autor')
        autores = []
        for a in autores_nodes:
            nome = a.find('NomeAutor')
            if nome is not None and nome.text:
                autores.append(nome.text.strip())
        return {
            'ementa': (ementa.text.strip() if ementa is not None and ementa.text else ''),
            'explicacao': (explicacao.text.strip() if explicacao is not None and explicacao.text else ''),
            'autores': ', '.join(autores) if autores else ''
        }
    except Exception:
        # Silencioso: falha de detalhes não deve quebrar fluxo principal
        return {}

def _load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}

def _save_cache(cache: dict):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception:
        pass

def _deduzir_identificacao(descricao: str) -> dict:
    """Tenta extrair tipo, número e ano da matéria a partir da descrição textual.
    Ex: "Emenda nº 721 (Substitutivo) ao PLP nº 108/2024" -> {'tipo': 'PLP', 'numero': '108', 'ano': '2024'}
    """
    if not descricao:
        return {}
    texto = descricao.replace('\n', ' ').replace(',', ' ').replace('  ', ' ')
    padrao = re.compile(r'(?P<tipo>PLP|PL|PEC|PLC|MPV|PDL|REQ|EMC)\s*n[ºo]\s*(?P<numero>\d+)[/\-](?P<ano>\d{4})', re.IGNORECASE)
    m = padrao.search(texto)
    if m:
        return {
            'siglaTipoMateria': m.group('tipo').upper(),
            'numeroMateria': m.group('numero'),
            'anoMateria': m.group('ano')
        }
    return {}

def _buscar_por_tipo_numero_ano(tipo: str, numero: str, ano: str) -> dict:
    """Tenta localizar matéria na listagem geral de votações para obter ementa (heurística)."""
    url = "https://legis.senado.leg.br/dadosabertos/votacao"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
        for vot in root.findall('.//Votacao'):
            t = vot.find('siglaTipoMateria')
            n = vot.find('numeroMateria')
            a = vot.find('anoMateria')
            if all([t is not None, n is not None, a is not None]):
                if t.text == tipo and n.text == numero and a.text == ano:
                    ementa = vot.find('ementaMateria').text if vot.find('ementaMateria') is not None else ''
                    resultado = vot.find('resultado').text if vot.find('resultado') is not None else ''
                    tipo_votacao = vot.find('descricaoVotacao').text if vot.find('descricaoVotacao') is not None else ''
                    return {
                        'ementa': ementa or '',
                        'resultado': resultado or '',
                        'tipo_votacao': tipo_votacao or ''
                    }
    except Exception:
        return {}
    return {}

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

        cache = _load_cache()
        for votacao_node in root_orientacoes.findall('.//votacoes'):
            descricao_materia = votacao_node.find('descricaoMateria').text or "Matéria Indisponível"
            data_sessao = votacao_node.find('dataInicioVotacao').text.split(' ')[0] if votacao_node.find('dataInicioVotacao') is not None else ""
            chave = descricao_materia.strip()

            codigo_materia = ''
            codigo_elem = votacao_node.find('codigoMateria')
            if codigo_elem is not None and codigo_elem.text:
                codigo_materia = codigo_elem.text.strip()

            # Match aproximado com o mapa de matérias detalhadas
            chaves_detalhadas = list(mapa_materias_detalhadas.keys())
            chave_proxima = get_close_matches(chave, chaves_detalhadas, n=1, cutoff=0.6)

            if chave_proxima:
                detalhes = mapa_materias_detalhadas.get(chave_proxima[0], {})
            else:
                detalhes = {}

            # Enriquecer com detalhes da matéria se tivermos o código
            if codigo_materia:
                if codigo_materia in cache:
                    extra = cache[codigo_materia]
                else:
                    extra = obter_detalhes_materia(codigo_materia)
                    if extra:
                        cache[codigo_materia] = extra
                if extra.get('ementa'): detalhes['ementa'] = extra['ementa']
                if extra.get('explicacao'): detalhes['explicacao'] = extra['explicacao']
                if extra.get('autores'): detalhes['autores'] = extra['autores']
            else:
                ident = _deduzir_identificacao(descricao_materia)
                if ident:
                    tentativa = _buscar_por_tipo_numero_ano(ident['siglaTipoMateria'], ident['numeroMateria'], ident['anoMateria'])
                    for k in ['ementa','resultado','tipo_votacao']:
                        if tentativa.get(k):
                            detalhes[k] = tentativa[k]

            ementa = detalhes.get("ementa", "")
            resultado = detalhes.get("resultado", "")
            tipo_votacao = detalhes.get("tipo_votacao", "")
            explicacao = detalhes.get("explicacao", "")
            autores = detalhes.get("autores", "")

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
                        "codigo_materia": codigo_materia,
                        "ementa": ementa,
                        "explicacao": explicacao,
                        "autores": autores,
                        "resultado": resultado,
                        "tipo_votacao": tipo_votacao
                    }
                }

        _save_cache(cache)
        return votacoes_processadas

    except requests.RequestException as e:
        st.error(f"Erro ao buscar dados de votações: {e}")
        return {}

    except ET.ParseError as e:
        st.error(f"Erro ao processar XML de votações: {e}")
        return {}
