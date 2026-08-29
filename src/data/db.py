"""Camada de persistência local (SQLite) para o corpus de avaliação do AgentAI.

O pipeline original mantém os discursos apenas em memória (cache do Streamlit), o que
impede montar um corpus estável para o gabarito de classificação e para as métricas de
avaliação. Este módulo materializa esses dados em um banco SQLite versionável em recorte,
com upsert idempotente por identificador oficial — reexecutar a coleta para o mesmo período
não duplica registros (requisito de reprodutibilidade, dimensão 4.1).

Tabelas:
- ``discursos``: um pronunciamento por linha, chaveado pelo ``codigo_pronunciamento``.
- ``votacoes``: uma votação nominal por linha (metadados da matéria + placar).
- ``votos``: um voto individual por linha, ligado à votação.

Uso programático::

    from src.data import db
    con = db.conectar("data/agentai.sqlite")
    db.criar_schema(con)
    db.upsert_discursos(con, lista_de_dicts)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

# Caminho padrão do banco (fora do versionamento; regenerável pela coleta).
CAMINHO_DB_PADRAO = Path("data/agentai.sqlite")

# Colunas persistidas para discursos, na ordem do INSERT. Mantê-las explícitas evita
# depender da ordem de um dict e documenta o schema em um único lugar.
COLUNAS_DISCURSO: Sequence[str] = (
    "codigo_pronunciamento",
    "data",
    "casa",
    "tipo_autor",
    "funcao_autor",
    "nome_autor",
    "partido",
    "uf",
    "cargo_autor",
    "orgao_autor",
    "resumo",
    "indexacao",
    "texto_integral_url",
    "codigo_sessao",
    "tipo_sessao",
    "data_sessao",
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS discursos (
    codigo_pronunciamento TEXT PRIMARY KEY,
    data                  TEXT,
    casa                  TEXT,
    tipo_autor            TEXT,
    funcao_autor          TEXT,
    nome_autor            TEXT,
    partido               TEXT,
    uf                    TEXT,
    cargo_autor           TEXT,
    orgao_autor           TEXT,
    resumo                TEXT,
    indexacao             TEXT,
    texto_integral_url    TEXT,
    codigo_sessao         TEXT,
    tipo_sessao           TEXT,
    data_sessao           TEXT,
    coletado_em           TEXT
);
CREATE INDEX IF NOT EXISTS idx_discursos_data ON discursos(data);
CREATE INDEX IF NOT EXISTS idx_discursos_tipo_autor ON discursos(tipo_autor);

CREATE TABLE IF NOT EXISTS votacoes (
    codigo_votacao   TEXT PRIMARY KEY,
    identificacao    TEXT,
    codigo_materia   TEXT,
    descricao_votacao TEXT,
    descricao_materia TEXT,
    ementa           TEXT,
    autores          TEXT,
    tipo_documento   TEXT,
    situacao_atual   TEXT,
    resultado        TEXT,
    qtd_sim          INTEGER,
    qtd_nao          INTEGER,
    qtd_abstencao    INTEGER,
    data_sessao      TEXT,
    coletado_em      TEXT
);

CREATE TABLE IF NOT EXISTS votos (
    codigo_votacao TEXT,
    parlamentar    TEXT,
    partido        TEXT,
    uf             TEXT,
    voto           TEXT,
    PRIMARY KEY (codigo_votacao, parlamentar)
);
CREATE INDEX IF NOT EXISTS idx_votos_votacao ON votos(codigo_votacao);

-- Classificação temática por LLM, chaveada por (discurso, modelo). Permitir vários
-- modelos (Mistral/Gemma/Qwen/Jurema...) lado a lado para comparação (dimensão 4.2).
CREATE TABLE IF NOT EXISTS classificacao_llm (
    id_discurso   TEXT,
    modelo        TEXT,
    categoria     TEXT,
    prompt_versao TEXT,
    criado_em     TEXT,
    PRIMARY KEY (id_discurso, modelo)
);
CREATE INDEX IF NOT EXISTS idx_clf_llm_modelo ON classificacao_llm(modelo);
"""


def conectar(caminho: str | Path = CAMINHO_DB_PADRAO) -> sqlite3.Connection:
    """Abre (criando o diretório se preciso) a conexão SQLite com row factory por nome."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(caminho))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    return con


def criar_schema(con: sqlite3.Connection) -> None:
    """Cria as tabelas/índices se ainda não existirem (idempotente)."""
    con.executescript(_SCHEMA)
    con.commit()


def upsert_discursos(con: sqlite3.Connection, registros: Iterable[dict]) -> int:
    """Insere/atualiza discursos por ``codigo_pronunciamento``. Retorna nº processado.

    Idempotente: reexecutar para o mesmo período sobrescreve os campos com os valores
    atuais da API, sem criar duplicatas.
    """
    agora = datetime.now().isoformat(timespec="seconds")
    cols = list(COLUNAS_DISCURSO) + ["coletado_em"]
    placeholders = ", ".join(["?"] * len(cols))
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "codigo_pronunciamento")
    sql = (
        f"INSERT INTO discursos ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(codigo_pronunciamento) DO UPDATE SET {updates}"
    )
    n = 0
    for reg in registros:
        valores = [reg.get(c, "") for c in COLUNAS_DISCURSO] + [agora]
        con.execute(sql, valores)
        n += 1
    con.commit()
    return n


def upsert_classificacao_llm(
    con: sqlite3.Connection,
    id_discurso: str,
    modelo: str,
    categoria: str,
    prompt_versao: str,
) -> None:
    """Grava/atualiza a categoria prevista por um modelo para um discurso (idempotente)."""
    con.execute(
        "INSERT INTO classificacao_llm (id_discurso, modelo, categoria, prompt_versao, criado_em) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(id_discurso, modelo) DO UPDATE SET "
        "categoria=excluded.categoria, prompt_versao=excluded.prompt_versao, criado_em=excluded.criado_em",
        (str(id_discurso), modelo, categoria, prompt_versao,
         datetime.now().isoformat(timespec="seconds")),
    )
    con.commit()


def contar(con: sqlite3.Connection, tabela: str) -> int:
    """Conta linhas de uma tabela (nome validado contra o schema conhecido)."""
    if tabela not in {"discursos", "votacoes", "votos", "classificacao_llm"}:
        raise ValueError(f"Tabela desconhecida: {tabela}")
    return con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
