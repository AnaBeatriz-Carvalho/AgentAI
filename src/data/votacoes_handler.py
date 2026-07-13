"""Busca e enriquecimento de votações nominais do Plenário do Senado.

Antes esta camada montava a votação a partir do XML de dois endpoints e casava as
matérias por similaridade de texto (`get_close_matches`), consultando ainda o endpoint
`/materia/{codigo}` (hoje **DEPRECATED**). O resultado era frágil: muitas votações
apareciam sem "sobre o que foi".

Agora usamos o JSON de `plenario/votacao/orientacaoBancada/{ini}/{fim}` — que já traz a
descrição do que foi votado (`descricaoVotacao`), a identificação da matéria
(`siglaTipoMateria`/`numeroMateria`/`anoMateria`), os votos individuais
(`votosParlamentar`) e o placar — e enriquecemos cada votação com o endpoint moderno
`/processo` (ementa, autoria, tipo de documento, situação atual e link do texto).
"""

import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from src.config.constants import (
    CACHE_TTL_VOTACOES,
    REQUEST_TIMEOUT,
    SENADO_API_PROCESSO,
    SENADO_API_VOTACOES,
    SENADO_HEADERS_JSON,
)
from src.utils.logger import get_logger

# Cache em disco dos detalhes de processo (evita rebater a API a cada rerun do Streamlit).
CACHE_PATH = Path("outputs/processos_cache.json")
logger = get_logger(__name__)


def _get_json(url: str) -> object:
    """GET + parse JSON com decode robusto de encoding.

    Os endpoints do Senado misturam UTF-8 e Latin-1 e às vezes anunciam o charset
    errado. Decodificamos os bytes crus tentando UTF-8 (estrito) e caindo para
    Latin-1, o que corrige a acentuação independentemente do endpoint.
    """
    resp = requests.get(url, headers=SENADO_HEADERS_JSON, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    raw = resp.content
    for enc in ("utf-8", "latin-1"):
        try:
            return json.loads(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return json.loads(raw.decode("latin-1", errors="replace"))


def _load_cache() -> dict:
    """Carrega o cache de detalhes de processos do arquivo."""
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            logger.debug(f"Failed to load cache: {e}")
    return {}


def _save_cache(cache: dict) -> None:
    """Salva o cache de detalhes de processos em arquivo."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.debug(f"Failed to save cache: {e}")


def obter_detalhes_processo(sigla: str, numero, ano) -> dict:
    """Consulta o endpoint moderno `/processo` por sigla/número/ano.

    Retorna um dicionário com ementa, autoria, tipo de documento, situação atual e
    link do texto integral. Dicionário vazio quando a matéria não é localizada.
    """
    if not (sigla and numero and ano):
        return {}
    identificacao = f"{sigla} {numero}/{ano}"
    url = f"{SENADO_API_PROCESSO}?sigla={sigla}&numero={numero}&ano={ano}"
    try:
        data = _get_json(url)
        if not data:
            return {}
        itens = data if isinstance(data, list) else [data]
        # Prefere o processo cuja identificação bate exatamente; senão usa o primeiro.
        proc = next((p for p in itens if p.get("identificacao") == identificacao), itens[0])
        return {
            "codigo_materia": str(proc.get("codigoMateria") or ""),
            "id_processo": str(proc.get("id") or ""),
            "identificacao": proc.get("identificacao") or identificacao,
            "ementa": (proc.get("ementa") or "").strip(),
            "autores": proc.get("autoria") or "",
            "tipo_documento": proc.get("tipoDocumento") or "",
            "situacao_atual": proc.get("situacaoAtual") or "",
            "data_apresentacao": proc.get("dataApresentacao") or "",
            "url_documento": proc.get("urlDocumento") or "",
            "tramitando": proc.get("tramitando") or "",
        }
    except Exception as e:
        logger.debug(f"Falha ao consultar processo {identificacao}: {e}")
        return {}


def _montar_votos(votacao: dict) -> pd.DataFrame:
    """Extrai os votos individuais de uma votação em um DataFrame padronizado."""
    votos = []
    for vp in votacao.get("votosParlamentar") or []:
        votos.append({
            "Parlamentar": vp.get("nomeParlamentar"),
            "Partido": vp.get("partido"),
            "UF": vp.get("uf"),
            "Voto": vp.get("voto"),
        })
    return pd.DataFrame(votos)


@st.cache_data(ttl=CACHE_TTL_VOTACOES)
def obter_votacoes_periodo(data_inicio, data_fim) -> dict:
    """Busca as votações nominais do Plenário no período, já enriquecidas.

    Retorna um dicionário `{rotulo: {"df_votos": DataFrame, "detalhes": {...}}}`, onde
    `rotulo` identifica a votação no seletor da interface e `detalhes` reúne o que a
    matéria propõe (ementa/autoria/situação) para exibição e para o LLM.
    """
    data_inicio_str = data_inicio.strftime("%Y%m%d")
    data_fim_str = data_fim.strftime("%Y%m%d")
    url = f"{SENADO_API_VOTACOES}/{data_inicio_str}/{data_fim_str}"

    try:
        data = _get_json(url)
    except requests.RequestException:
        st.info("⚠️ Não foi possível recuperar as votações neste momento.")
        st.caption("Verifique sua conexão e tente novamente.")
        return {}
    except (json.JSONDecodeError, ValueError):
        st.info("⚠️ Houve um problema ao processar os dados das votações.")
        st.caption("Tente novamente com um período diferente.")
        return {}

    votacoes = data.get("votacoes", []) if isinstance(data, dict) else []
    cache = _load_cache()
    resultado_final: dict = {}

    for votacao in votacoes:
        df_votos = _montar_votos(votacao)
        if df_votos.empty:
            continue

        tipo = votacao.get("siglaTipoMateria")
        numero = votacao.get("numeroMateria")
        ano = votacao.get("anoMateria")
        descricao_votacao = (votacao.get("descricaoVotacao") or "").strip()
        descricao_materia = (votacao.get("descricaoMateria") or "Matéria indisponível").strip()
        data_sessao = (votacao.get("dataInicioVotacao") or "").split("T")[0]

        # Enriquecimento pelo processo moderno (com cache por identificação).
        chave_proc = f"{tipo} {numero}/{ano}"
        if chave_proc in cache:
            proc = cache[chave_proc]
        else:
            proc = obter_detalhes_processo(tipo, numero, ano)
            if proc:
                cache[chave_proc] = proc

        # Placar e resultado desta votação específica (a partir das contagens oficiais).
        sim = int(votacao.get("qtdVotosSim") or 0)
        nao = int(votacao.get("qtdVotosNao") or 0)
        abstencao = int(votacao.get("qtdVotosAbstencao") or 0)
        if sim > nao:
            resultado = f"Aprovada ({sim} a {nao})"
        elif nao > sim:
            resultado = f"Rejeitada ({nao} a {sim})"
        else:
            resultado = f"Empate ({sim} a {nao})"

        detalhes = {
            "codigo_materia": proc.get("codigo_materia", ""),
            "identificacao": proc.get("identificacao", "") or chave_proc,
            "descricao_votacao": descricao_votacao,
            "descricao_materia": descricao_materia,
            "ementa": proc.get("ementa", ""),
            "autores": proc.get("autores", ""),
            "tipo_documento": proc.get("tipo_documento", ""),
            "situacao_atual": proc.get("situacao_atual", ""),
            "data_apresentacao": proc.get("data_apresentacao", ""),
            "url_documento": proc.get("url_documento", ""),
            "tipo_votacao": "Nominal",
            "resultado": resultado,
            "placar": {"Sim": sim, "Não": nao, "Abstenção": abstencao},
            "data_sessao": data_sessao,
        }

        # Rótulo do seletor: identificação + o que foi votado + data (garantindo unicidade).
        resumo = descricao_votacao or descricao_materia
        rotulo_base = f"{detalhes['identificacao']} — {resumo}"
        if len(rotulo_base) > 130:
            rotulo_base = rotulo_base[:127] + "..."
        if data_sessao:
            rotulo_base = f"{rotulo_base}  ·  {data_sessao}"
        rotulo = rotulo_base
        sufixo = 2
        while rotulo in resultado_final:
            rotulo = f"{rotulo_base} ({sufixo})"
            sufixo += 1

        resultado_final[rotulo] = {"df_votos": df_votos, "detalhes": detalhes}

    _save_cache(cache)
    return resultado_final
