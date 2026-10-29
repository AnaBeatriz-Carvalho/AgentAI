"""Orquestra a coleta de uma câmara SAPL: busca na API e devolve DataFrames normalizados.

Retorna também ``avisos`` em linguagem simples sobre lacunas de dados (ex.: câmara que
não registra votações no sistema). Mostrar essas lacunas ao cidadão faz parte da
transparência: a ausência de dado é informação, não erro do app.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.sapl import normalizacao as nz
from src.sapl.client import SaplClient, SaplErro
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DadosCamara:
    url_base: str
    materias: pd.DataFrame
    vereadores: pd.DataFrame
    votacoes: pd.DataFrame
    avisos: list[str] = field(default_factory=list)
    votacoes_indisponiveis: bool = False


def _seguro(rotulo: str, func, avisos: list[str]) -> list[dict]:
    """Executa uma listagem auxiliar; se falhar, registra aviso e segue com lista vazia."""
    try:
        return func()
    except SaplErro as e:
        logger.warning(f"SAPL: falha ao obter {rotulo}: {e}")
        avisos.append(f"Não foi possível obter {rotulo} desta câmara; alguns campos ficarão em branco.")
        return []


def carregar_camara(
    url_base: str,
    data_inicio: date,
    data_fim: date,
    client: SaplClient | None = None,
) -> DadosCamara:
    """Coleta matérias, vereadores e votações de uma câmara no período.

    Falha na listagem de matérias propaga ``SaplErro`` (sem elas não há o que mostrar);
    falhas nas tabelas auxiliares viram avisos.
    """
    client = client or SaplClient(url_base)
    ini, fim = data_inicio.isoformat(), data_fim.isoformat()
    avisos: list[str] = []

    materias_raw = client.materias(ini, fim)
    tipos = nz.mapa_tipos(_seguro("os tipos de matéria", client.tipos_materia, avisos))
    parlamentares_raw = _seguro("a lista de vereadores", client.parlamentares, avisos)
    autores = nz.mapa_autores(_seguro("os autores", client.autores, avisos), parlamentares_raw)
    partidos = nz.mapa_partidos(_seguro("os partidos", client.partidos, avisos))
    partido_por_parl = nz.partido_atual_por_parlamentar(
        _seguro("as filiações partidárias", client.filiacoes, avisos), partidos
    )
    n_avisos = len(avisos)
    votacoes_raw = _seguro("as votações", lambda: client.votacoes(ini, fim), avisos)
    votacoes_indisponiveis = len(avisos) > n_avisos

    df_materias = nz.normalizar_materias(materias_raw, tipos, autores, partido_por_parl, client.url_base)
    df_vereadores = nz.normalizar_vereadores(parlamentares_raw, partido_por_parl, client.url_base)
    df_votacoes = nz.normalizar_votacoes(votacoes_raw, df_materias, ini, fim)

    if df_materias.empty:
        avisos.append("Nenhuma matéria foi registrada no SAPL desta câmara no período escolhido.")
    elif (df_materias["Texto original"] == "").mean() > 0.5:
        avisos.append("Mais da metade das matérias do período não tem o texto original anexado no sistema.")
    if df_votacoes.empty and not votacoes_indisponiveis:
        avisos.append(
            "Esta câmara não registrou votações no SAPL para o período. Isso não significa que "
            "não houve votação, apenas que o resultado não foi lançado no sistema."
        )

    return DadosCamara(
        client.url_base, df_materias, df_vereadores, df_votacoes, avisos, votacoes_indisponiveis
    )
