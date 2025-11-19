import pandas as pd
import requests
from datetime import timedelta
import time
import json
import streamlit as st
import google.generativeai as genai
import xml.etree.ElementTree as ET
import os
import hashlib
import random

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
    batch_size: int = 10,
    sleep_between_batches: float = 5.0,
    max_retries: int = 5,
    base_delay: float = 3.0,
    debug_save_raw: bool = False,
):
    """
    Função principal que extrai pronunciamentos da API do Senado e os classifica usando Gemini.
    """
    df_final = extrair_discursos_senado(data_inicio, data_fim)
    if df_final.empty:
        return df_final
        
    df_classificado = classificar_tema_discursos_com_gemini(
        df_final,
        batch_size=batch_size,
        sleep_between_batches=sleep_between_batches,
        max_retries=max_retries,
        base_delay=base_delay,
        debug_save_raw=debug_save_raw,
    )
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


def _discursos_cache_path() -> str:
    return os.path.join('outputs', 'discursos_cache.json')


def clear_discursos_cache() -> bool:
    """Remove o cache de classificação de discursos do disco."""
    path = _discursos_cache_path()
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    except Exception:
        return False


def classificar_tema_discursos_com_gemini(
    df: pd.DataFrame,
    batch_size: int = 10,
    sleep_between_batches: float = 5.0,
    max_retries: int = 5,
    base_delay: float = 3.0,
    debug_save_raw: bool = False,
) -> pd.DataFrame:
    """
    Classifica discursos em lote (batch) com uma pausa entre cada lote
    para evitar os limites de requisição da API (rate limiting).
    """
    # Inicializa sempre com modelo flash estável; evita impacto das mudanças de votação
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
    except Exception as e:
        st.error(f"Erro ao inicializar o modelo Gemini. Verifique sua API Key. Erro: {e}")
        return df

    # ------- Cache simples em disco para reduzir chamadas -------
    cache_path = _discursos_cache_path()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    else:
        cache = {}

    def resumo_key(txt: str) -> str:
        return hashlib.sha256((txt or '').encode('utf-8')).hexdigest()

    discursos = df['Resumo'].fillna("").tolist()
    temas_previstos: list[str] = [None] * len(discursos)

    # Preenche do cache
    for idx, r in enumerate(discursos):
        k = resumo_key(r)
        tema_cached = cache.get(k)
        if tema_cached:
            temas_previstos[idx] = tema_cached

    # Lista de índices a classificar
    pendentes = [i for i, v in enumerate(temas_previstos) if not v]

    if not pendentes:
        df['Tema'] = temas_previstos
        return df

    progress_bar = st.progress(0, text="Classificando discursos em lotes com o Agente Gemini...")

    # Loop simples em lotes fixos (versão anterior estável)
    for bstart in range(0, len(pendentes), batch_size):
        lote_indices = pendentes[bstart:bstart + batch_size]
        batch_resumos = [discursos[i] for i in lote_indices]

        prompt_batch = (
            "Analise cada um dos resumos de discurso abaixo, numerados de 0 a {}.\n".format(len(batch_resumos) - 1)
            + "Classifique cada um em UMA das seguintes categorias: {}.\n".format(', '.join(TEMAS_DEFINIDOS))
            + "Responda somente com uma lista JSON de objetos no formato "
              "[{\"index\": 0, \"tema\": \"Saúde\"}, {\"index\": 1, \"tema\": \"Economia\"}].\n\n"
        )

        for j, resumo in enumerate(batch_resumos):
            # Usar até 600 caracteres como antes
            prompt_batch += f"Discurso {j}: \"{resumo[:600]}\"\n"

        # Retries com backoff quando 429
        tentativa = 0
        resultados_batch = None
        while tentativa < max_retries:
            try:
                response = model.generate_content(prompt_batch)
                response_text = response.text.strip()
                response_text = response_text.replace("```json", "").replace("```", "")

                if '[' in response_text and ']' in response_text:
                    inicio = response_text.find('[')
                    fim = response_text.rfind(']') + 1
                    bruto = response_text[inicio:fim]
                else:
                    bruto = response_text

                try:
                    resultados_batch = json.loads(bruto)
                except json.JSONDecodeError:
                    corrigido = bruto.replace("'", '"').replace(',\n]', '\n]')
                    try:
                        resultados_batch = json.loads(corrigido)
                    except Exception:
                        resultados_batch = []
                # Salva resposta bruta para debug se habilitado
                if debug_save_raw:
                    try:
                        os.makedirs(os.path.join('outputs', 'debug_discursos'), exist_ok=True)
                        lote_num = bstart // (batch_size if batch_size else 1) + 1
                        fname = os.path.join('outputs', 'debug_discursos', f"lote_{lote_num}_{int(time.time())}.txt")
                        with open(fname, 'w', encoding='utf-8') as f:
                            f.write(response_text)
                    except Exception:
                        pass
                break
            except Exception as e:
                msg = str(e)
                if '429' in msg or 'Resource exhausted' in msg:
                    sleep_s = base_delay * (2 ** tentativa) + random.uniform(0, 1.5)
                    st.warning(f"Limite de taxa atingido no lote {bstart//batch_size + 1}. Tentando novamente em {sleep_s:.1f}s...")
                    time.sleep(sleep_s)
                    tentativa += 1
                    continue
                else:
                    st.error(f"Erro ao processar lote {bstart//batch_size + 1}: {e}")
                    resultados_batch = []
                    break

        temas_lote = ["Outros"] * len(batch_resumos)
        for item in (resultados_batch or []):
            if isinstance(item, dict) and 'index' in item and 'tema' in item:
                idx_local = item['index']
                tema = item['tema']
                if isinstance(idx_local, int) and 0 <= idx_local < len(temas_lote):
                    temas_lote[idx_local] = tema if tema in TEMAS_DEFINIDOS else "Outros"

        # Se não conseguimos nada parseável após retries, marca como erro
        if resultados_batch is not None and len(resultados_batch) == 0 and tentativa >= max_retries:
            temas_lote = ["Erro na Classificação"] * len(batch_resumos)

        # Atribui aos índices globais e atualiza cache
        for offset, tema in enumerate(temas_lote):
            gi = lote_indices[offset]
            temas_previstos[gi] = tema
            cache[resumo_key(discursos[gi])] = tema

        # Persistir cache incrementalmente para resiliência
        try:
            os.makedirs('outputs', exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        progresso = (bstart + len(lote_indices)) / len(pendentes)
        progress_bar.progress(min(progresso, 1.0), text=f"Classificando lote {bstart//batch_size + 1}...")
        time.sleep(sleep_between_batches)

    # Preenche algum restante nulo como 'Outros'
    df['Tema'] = [t if t else 'Outros' for t in temas_previstos]
    progress_bar.empty()
    return df
