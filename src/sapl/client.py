"""Cliente HTTP mínimo para a API REST do SAPL 3.x.

A API usa Django REST Framework com paginação própria::

    {"pagination": {"next_page": 2, "total_entries": 7543, ...}, "results": [...]}

e filtros do django-filter na query string (ex.: ``data_apresentacao__gte=2026-01-01``,
``o=-data_apresentacao``). O cliente percorre as páginas pelo parâmetro ``page`` (não
segue o link ``next``, que algumas instâncias devolvem com ``http://``) e para em
``max_paginas`` para não varrer bases inteiras por engano.
"""

from __future__ import annotations

import json
import time
from typing import Iterator, Optional

import requests

from src.config.constants import REQUEST_TIMEOUT
from src.sapl.camaras import normalizar_url_base

SAPL_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "AgentAI/1.0 (consulta a dados legislativos abertos)",
}

# Endpoints usados pelo app (relativos a ``/api/``).
EP_MATERIAS = "materia/materialegislativa/"
EP_TIPOS_MATERIA = "materia/tipomaterialegislativa/"
EP_AUTORES = "base/autor/"
EP_PARLAMENTARES = "parlamentares/parlamentar/"
EP_FILIACOES = "parlamentares/filiacao/"
EP_PARTIDOS = "parlamentares/partido/"
EP_VOTACOES = "sessao/registrovotacao/"

# Limite padrão de páginas por listagem (10 itens por página na maioria das instâncias).
MAX_PAGINAS_PADRAO = 60
# Pausa entre páginas: as instâncias são servidores modestos e limitam rajadas.
PAUSA_ENTRE_PAGINAS = 0.2


class SaplErro(RuntimeError):
    """Falha ao consultar uma instância SAPL (rede, HTTP ou formato inesperado)."""


class SaplClient:
    """Acesso somente leitura a uma instância SAPL."""

    def __init__(
        self,
        url_base: str,
        session: Optional[requests.Session] = None,
        timeout: int = REQUEST_TIMEOUT,
        pausa: float = PAUSA_ENTRE_PAGINAS,
    ):
        self.url_base = normalizar_url_base(url_base)
        self.session = session or requests.Session()
        self.timeout = timeout
        self.pausa = pausa

    def _url(self, endpoint: str) -> str:
        return f"{self.url_base}/api/{endpoint.lstrip('/')}"

    def _get_json(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = self._url(endpoint)
        try:
            resp = self.session.get(url, params=params, headers=SAPL_HEADERS, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise SaplErro(f"Falha ao acessar {url}: {e}") from e
        raw = resp.content
        for enc in ("utf-8", "latin-1"):
            try:
                dados = json.loads(raw.decode(enc))
                break
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        else:
            raise SaplErro(f"Resposta não é JSON em {url}")
        if not isinstance(dados, dict):
            raise SaplErro(f"Formato inesperado em {url}")
        return dados

    def listar(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        max_paginas: int = MAX_PAGINAS_PADRAO,
    ) -> Iterator[dict]:
        """Itera sobre todos os registros de um endpoint paginado."""
        params = dict(params or {})
        pagina = 1
        for _ in range(max_paginas):
            params["page"] = pagina
            dados = self._get_json(endpoint, params)
            for item in dados.get("results") or []:
                yield item
            proxima = (dados.get("pagination") or {}).get("next_page")
            if not proxima or proxima == pagina:
                return
            pagina = int(proxima)
            if self.pausa:
                time.sleep(self.pausa)

    def listar_tudo(self, endpoint: str, params: Optional[dict] = None,
                    max_paginas: int = MAX_PAGINAS_PADRAO) -> list[dict]:
        return list(self.listar(endpoint, params, max_paginas))

    # --- Atalhos por recurso -------------------------------------------------------

    def materias(self, data_inicio: str, data_fim: str, max_paginas: int = MAX_PAGINAS_PADRAO) -> list[dict]:
        """Matérias apresentadas no período (datas ISO ``AAAA-MM-DD``), mais recentes primeiro."""
        return self.listar_tudo(
            EP_MATERIAS,
            {
                "data_apresentacao__gte": data_inicio,
                "data_apresentacao__lte": data_fim,
                "o": "-data_apresentacao",
            },
            max_paginas,
        )

    def votacoes(self, data_inicio: str, data_fim: str, max_paginas: int = 20) -> list[dict]:
        """Registros de votação no período. O filtro por data é reforçado na normalização,
        porque nem toda instância aplica ``data_hora__gte`` do mesmo jeito.

        O fim do período vai como ``AAAA-MM-DD 23:59:59``, com espaço: o SAPL rejeita o
        formato ISO com ``T`` (400, "Informe uma data/hora válida")."""
        return self.listar_tudo(
            EP_VOTACOES,
            {"data_hora__gte": data_inicio, "data_hora__lte": f"{data_fim} 23:59:59"},
            max_paginas,
        )

    def tipos_materia(self) -> list[dict]:
        return self.listar_tudo(EP_TIPOS_MATERIA)

    def autores(self) -> list[dict]:
        return self.listar_tudo(EP_AUTORES)

    def parlamentares(self) -> list[dict]:
        return self.listar_tudo(EP_PARLAMENTARES)

    def filiacoes(self) -> list[dict]:
        return self.listar_tudo(EP_FILIACOES)

    def partidos(self) -> list[dict]:
        return self.listar_tudo(EP_PARTIDOS)
