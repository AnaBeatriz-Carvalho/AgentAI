"""Transforma o JSON bruto do SAPL em DataFrames prontos para a interface e o chat.

Funções puras (sem rede), para que a lógica de junção seja testável isoladamente.

Pontos de atenção do modelo de dados do SAPL:
- ``materia.autores`` aponta para ``base/autor`` (não para ``parlamentar``). O autor
  liga ao vereador por ``object_id`` quando é um parlamentar; também pode ser a Mesa,
  uma comissão ou o Executivo.
- ``materia.tipo`` é uma chave para ``tipomaterialegislativa`` (sigla/descrição).
- O partido não fica no parlamentar: vem da filiação sem ``data_desfiliacao``.
- Vereadores podem ter telefone e e-mail pessoal cadastrados. Para o cidadão expomos só
  o e-mail institucional (domínio ``.leg.br``) e nenhum telefone.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

import pandas as pd

from src.eval.categorias import classificar_keyword

COLUNAS_MATERIAS = [
    "id_materia", "Identificação", "Tipo", "Data", "Ementa", "Autores",
    "Partido", "Tema", "Em tramitação", "Link", "Texto original",
]
COLUNAS_VEREADORES = [
    "id_parlamentar", "Vereador", "Nome completo", "Partido", "Em exercício",
    "Profissão", "E-mail institucional", "Foto", "Página",
]
COLUNAS_VOTACOES = [
    "id_votacao", "Matéria", "id_materia", "Data", "Resultado", "Sim", "Não",
    "Abstenções", "Observação",
]


def _norm_nome(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).lower().split())


def mapa_tipos(tipos: list[dict]) -> dict[int, dict]:
    """``{id: {"sigla", "descricao"}}`` dos tipos de matéria."""
    return {
        t["id"]: {"sigla": (t.get("sigla") or "").strip(), "descricao": (t.get("descricao") or "").strip()}
        for t in tipos if "id" in t
    }


def mapa_partidos(partidos: list[dict]) -> dict[int, str]:
    """``{id: sigla}`` dos partidos."""
    return {p["id"]: (p.get("sigla") or p.get("nome") or "").strip() for p in partidos if "id" in p}


def _sigla_do_str_filiacao(texto: str) -> str:
    """Fallback: ``"Fulano - PSD - Partido Social Democrático"`` → ``"PSD"``."""
    partes = [p.strip() for p in str(texto or "").split(" - ")]
    return partes[1] if len(partes) >= 3 else ""


def partido_atual_por_parlamentar(filiacoes: list[dict], partidos: dict[int, str]) -> dict[int, str]:
    """Partido vigente de cada parlamentar: filiação ativa (sem desfiliação) mais recente."""
    vigentes: dict[int, tuple[str, str]] = {}
    for f in filiacoes:
        if f.get("data_desfiliacao"):
            continue
        parl = f.get("parlamentar")
        if parl is None:
            continue
        sigla = partidos.get(f.get("partido")) or _sigla_do_str_filiacao(f.get("__str__"))
        data = f.get("data") or ""
        if parl not in vigentes or data >= vigentes[parl][0]:
            vigentes[parl] = (data, sigla)
    return {parl: sigla for parl, (_, sigla) in vigentes.items() if sigla}


def mapa_autores(autores: list[dict], parlamentares: list[dict]) -> dict[int, dict]:
    """``{id_autor: {"nome", "parlamentar_id"}}``.

    Só liga o autor a um vereador quando ``object_id`` existe entre os parlamentares e o
    nome confere, para não confundir com outros tipos de autor (Executivo, comissões),
    cujo ``object_id`` aponta para outra tabela e pode colidir numericamente.
    """
    nomes_parl = {p["id"]: _norm_nome(p.get("nome_parlamentar")) for p in parlamentares if "id" in p}
    saida: dict[int, dict] = {}
    for a in autores:
        if "id" not in a:
            continue
        nome = (a.get("nome") or a.get("__str__") or "").strip()
        obj = a.get("object_id")
        parlamentar_id = obj if obj in nomes_parl and nomes_parl[obj] == _norm_nome(nome) else None
        saida[a["id"]] = {"nome": nome, "parlamentar_id": parlamentar_id}
    return saida


def _email_institucional(email: str) -> str:
    email = (email or "").strip()
    return email if re.search(r"@[\w.-]+\.leg\.br$", email, flags=re.IGNORECASE) else ""


def normalizar_vereadores(
    parlamentares: list[dict],
    partido_por_parl: dict[int, str],
    url_base: str,
) -> pd.DataFrame:
    linhas = []
    for p in parlamentares:
        pid = p.get("id")
        linhas.append({
            "id_parlamentar": pid,
            "Vereador": (p.get("nome_parlamentar") or p.get("__str__") or "").strip(),
            "Nome completo": (p.get("nome_completo") or "").strip(),
            "Partido": partido_por_parl.get(pid, ""),
            "Em exercício": bool(p.get("ativo")),
            "Profissão": (p.get("profissao") or "").strip(),
            "E-mail institucional": _email_institucional(p.get("email")),
            "Foto": p.get("fotografia") or "",
            "Página": f"{url_base}/parlamentar/{pid}" if pid is not None else "",
        })
    df = pd.DataFrame(linhas, columns=COLUNAS_VEREADORES)
    if not df.empty:
        df = df.sort_values(["Em exercício", "Vereador"], ascending=[False, True]).reset_index(drop=True)
    return df


def _identificacao(materia: dict, tipos: dict[int, dict]) -> str:
    tipo = tipos.get(materia.get("tipo"), {})
    sigla = tipo.get("sigla") or tipo.get("descricao") or ""
    numero, ano = materia.get("numero"), materia.get("ano")
    if sigla and numero is not None and ano:
        return f"{sigla} {numero}/{ano}"
    return str(materia.get("__str__") or "").strip()


def normalizar_materias(
    materias: list[dict],
    tipos: dict[int, dict],
    autores: dict[int, dict],
    partido_por_parl: dict[int, str],
    url_base: str,
) -> pd.DataFrame:
    linhas = []
    for m in materias:
        mid = m.get("id")
        nomes, siglas = [], []
        for aid in m.get("autores") or []:
            autor = autores.get(aid)
            if not autor:
                continue
            nomes.append(autor["nome"])
            sigla = partido_por_parl.get(autor["parlamentar_id"]) if autor["parlamentar_id"] is not None else None
            if sigla and sigla not in siglas:
                siglas.append(sigla)
        ementa = " ".join(str(m.get("ementa") or "").split())
        linhas.append({
            "id_materia": mid,
            "Identificação": _identificacao(m, tipos),
            "Tipo": tipos.get(m.get("tipo"), {}).get("descricao", ""),
            "Data": m.get("data_apresentacao"),
            "Ementa": ementa,
            "Autores": ", ".join(nomes),
            "Partido": ", ".join(siglas),
            "Tema": classificar_keyword(ementa) if ementa else "Outros",
            "Em tramitação": bool(m.get("em_tramitacao")),
            "Link": f"{url_base}/materia/{mid}" if mid is not None else "",
            "Texto original": m.get("texto_original") or "",
        })
    df = pd.DataFrame(linhas, columns=COLUNAS_MATERIAS)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    if not df.empty:
        df = df.sort_values("Data", ascending=False, kind="stable").reset_index(drop=True)
    return df


def _resultado_do_str(texto: str) -> str:
    """``"... - Votação: Aprovado"`` → ``"Aprovado"``."""
    m = re.search(r"Vota[çc][ãa]o:\s*(.+)$", str(texto or ""))
    return m.group(1).strip() if m else ""


def _materia_do_str(texto: str) -> str:
    """Extrai a matéria do rótulo do registro de votação (entre ``N - `` e `` em ``)."""
    m = re.search(r":\s*\d+\s*-\s*(.+?)\s+em\s+", str(texto or ""))
    return m.group(1).strip() if m else ""


def normalizar_votacoes(
    votacoes: list[dict],
    df_materias: Optional[pd.DataFrame],
    data_inicio: str,
    data_fim: str,
) -> pd.DataFrame:
    ident = {}
    if df_materias is not None and not df_materias.empty:
        ident = dict(zip(df_materias["id_materia"], df_materias["Identificação"]))
    linhas = []
    for v in votacoes:
        data = str(v.get("data_hora") or "")[:10]
        if data and not (data_inicio <= data <= data_fim):
            continue
        mid = v.get("materia")
        linhas.append({
            "id_votacao": v.get("id"),
            "Matéria": ident.get(mid) or _materia_do_str(v.get("__str__")),
            "id_materia": mid,
            "Data": data,
            "Resultado": _resultado_do_str(v.get("__str__")),
            "Sim": v.get("numero_votos_sim"),
            "Não": v.get("numero_votos_nao"),
            "Abstenções": v.get("numero_abstencoes"),
            "Observação": (v.get("observacao") or "").strip(),
        })
    df = pd.DataFrame(linhas, columns=COLUNAS_VOTACOES)
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    if not df.empty:
        df = df.sort_values("Data", ascending=False, kind="stable").reset_index(drop=True)
    return df
