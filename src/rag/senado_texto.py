"""Busca o texto integral de um pronunciamento na API de Dados Abertos do Senado.

Endpoint: GET {SENADO_API_BASE}/discurso/texto-integral/{codigoPronunciamento}
Retorna o discurso completo em texto plano — o conteúdo ideal para indexar no RAG.

Em qualquer falha (HTTP, timeout, corpo vazio) a função devolve string vazia; o indexador
é quem decide o fallback (usar o `Resumo` do discurso), garantindo que nenhum discurso fique
de fora do índice.
"""

import requests

from src.config.constants import SENADO_API_TEXTO_INTEGRAL, SENADO_HEADERS, REQUEST_TIMEOUT
from src.utils.logger import get_logger

logger = get_logger(__name__)

# O endpoint responde texto plano; não pedimos XML como no resto da API.
_HEADERS_TEXTO = {
    "Accept": "text/plain, */*",
    "User-Agent": SENADO_HEADERS.get("User-Agent", "Mozilla/5.0"),
}


def buscar_texto_integral(codigo: str, timeout: int = REQUEST_TIMEOUT) -> str:
    """Retorna o texto integral do pronunciamento `codigo`, ou "" se indisponível."""
    codigo = str(codigo or "").strip()
    if not codigo:
        return ""

    url = f"{SENADO_API_TEXTO_INTEGRAL}/{codigo}"
    try:
        resp = requests.get(url, headers=_HEADERS_TEXTO, timeout=timeout)
        resp.raise_for_status()
        texto = (resp.text or "").strip()
        if not texto:
            logger.debug(f"Texto integral vazio para o pronunciamento {codigo}.")
        return texto
    except requests.RequestException as e:
        logger.warning(f"Falha ao buscar texto integral do pronunciamento {codigo}: {e}")
        return ""
