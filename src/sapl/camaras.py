"""Registro das Casas Legislativas com SAPL conhecidas pelo app.

Lista inicial a partir da página do Interlegis de órgãos atendidos com SAPL em Sergipe
(https://www12.senado.leg.br/interlegis/orgaosatendidos?servico=SAPL&uf=SE).
A interface também aceita uma URL informada pelo usuário, então esta lista é só um
atalho; não precisa estar completa.
"""

from __future__ import annotations

from urllib.parse import urlparse

CAMARAS_SAPL: dict[str, str] = {
    "Lagarto (SE)": "https://sapl.lagarto.se.leg.br",
    "Gararu (SE)": "https://sapl.gararu.se.leg.br",
    "Estância (SE)": "https://sapl.estancia.se.leg.br",
}


def normalizar_url_base(url: str) -> str:
    """Valida e normaliza a URL base de uma instância SAPL.

    Aceita ``sapl.cidade.uf.leg.br`` sem esquema, remove barra final e um eventual
    sufixo ``/api``. Levanta ``ValueError`` para entradas que não parecem um host.
    """
    url = (url or "").strip()
    if not url:
        raise ValueError("Informe a URL do SAPL da câmara.")
    if "://" not in url:
        url = "https://" + url
    partes = urlparse(url)
    if partes.scheme not in {"http", "https"} or not partes.netloc or "." not in partes.netloc:
        raise ValueError(f"URL inválida para o SAPL: {url}")
    caminho = partes.path.rstrip("/")
    if caminho.endswith("/api"):
        caminho = caminho[: -len("/api")]
    return f"{partes.scheme}://{partes.netloc}{caminho}"
