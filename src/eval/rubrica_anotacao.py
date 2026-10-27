"""Rubrica guiada da anotação de geração: perguntas objetivas que levam às notas.

Traduz as definições do `codebook_anotacao.md` em perguntas de decisão. A anotadora
responde às perguntas e a nota de suporte semântico (1 a 4) e a recusa (0/1) são
derivadas por regras fixas. A anotadora pode ajustar a nota derivada, com justificativa
obrigatória; resposta, nota derivada, nota final e justificativa ficam registradas.

Este módulo não lê a chave dos modelos nem as notas do LLM-juiz.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- perguntas

ACERTO_COM_RESPOSTA = {
    "pergunta": "A resposta traz a informação que a pergunta pede, de acordo com o gold?",
    "opcoes": {
        "completo": "Sim, de forma completa e precisa",
        "parcial": "Sim, mas com lacunas, imprecisões pequenas ou de forma genérica",
        "nao": "Não traz a informação pedida",
    },
}

ACERTO_SEM_RESPOSTA = {
    "pergunta": "A resposta reconhece que a informação pedida não existe nos dados?",
    "opcoes": {
        "completo": "Sim, com clareza",
        "parcial": "Reconhece, mas também responde em parte como se soubesse",
        "nao": "Não: responde como se a informação existisse",
    },
}

ERRO = {
    "pergunta": ("A resposta afirma como verdade algo que contradiz o gold ou que não tem "
                 "base nele (nome, número, data, tema, autor)?"),
    "opcoes": {
        "nao": "Não",
        "secundario": "Sim, mas só em detalhe secundário",
        "principal": "Sim, no ponto principal da pergunta",
    },
}

SOBRA = {
    "pergunta": "Apesar desse erro, a resposta traz alguma informação correta e relevante para a pergunta?",
    "opcoes": {"sim": "Sim", "nao": "Não"},
}

PT_FORMAL = {
    "pergunta": "Como está o português (gramática, coesão, registro formal)?",
    "opcoes": {
        5: "Impecável",
        4: "Pequenos deslizes",
        3: "Erros perceptíveis, mas legível",
        2: "Vários erros que atrapalham a leitura",
        1: "Incompreensível ou muito informal",
    },
}

COMPLETUDE = {
    "pergunta": "Quanto do que a pergunta pede a resposta cobre? (independente de estar certo)",
    "opcoes": {
        5: "Cobre todos os aspectos pedidos",
        4: "Cobre quase tudo, falta detalhe pequeno",
        3: "Cobre o principal, deixa pontas soltas",
        2: "Cobre pouco do que foi pedido",
        1: "Responde muito parcialmente ou foge do pedido",
    },
}


def sem_resposta(tem_resposta_no_corpus: str) -> bool:
    return str(tem_resposta_no_corpus).strip() == "Não"


def pergunta_acerto(tem_resposta_no_corpus: str) -> dict:
    return ACERTO_SEM_RESPOSTA if sem_resposta(tem_resposta_no_corpus) else ACERTO_COM_RESPOSTA


# ---------------------------------------------------------------- regras

@dataclass
class Derivacao:
    suporte: int | None
    recusa: str          # "0", "1" ou "n/a"
    aviso: str = ""


def derivar(tem_resposta_no_corpus: str, acerto: str | None, erro: str | None,
            sobra: str | None = None) -> Derivacao:
    """Aplica as regras do codebook às respostas da rubrica.

    Suporte semântico:
      erro no ponto principal  -> 2 se sobra informação correta relevante, senão 1
      erro só em detalhe       -> 3
      sem erro                 -> 4 se completa e precisa; 3 se parcial/genérica ou se
                                  não traz o fato pedido sem afirmar nada falso
    Recusa (só perguntas sem resposta no corpus): 1 se reconhece a ausência, senão 0.
    """
    sem = sem_resposta(tem_resposta_no_corpus)
    recusa = "n/a"
    if sem and acerto in ("completo", "parcial", "nao"):
        recusa = "0" if acerto == "nao" else "1"

    if acerto is None or erro is None:
        return Derivacao(None, recusa, "Responda às perguntas de suporte.")
    if sem and acerto == "nao" and erro == "nao":
        return Derivacao(None, recusa, (
            "Inconsistente: se a resposta trata a informação como existente, ela afirma algo "
            "sem base no gold. Revise a pergunta sobre afirmações falsas."))
    if erro == "principal":
        if sobra is None:
            return Derivacao(None, recusa, "Responda se sobra informação correta e relevante.")
        return Derivacao(2 if sobra == "sim" else 1, recusa)
    if erro == "secundario":
        return Derivacao(3, recusa)
    return Derivacao(4 if acerto == "completo" else 3, recusa)


# ---------------------------------------------------------------- arquivos

NOTAS = ("suporte_semantico", "recusa_correta", "pt_formal", "completude", "observacao")
CAMPOS_DECISAO = ["anotacao_id", "acerto", "erro", "sobra", "suporte_derivado",
                  "suporte_final", "ajuste_manual", "justificativa_ajuste", "salvo_em"]


def ler_planilha(path: Path) -> tuple[list[str], list[dict], str]:
    raw = Path(path).read_bytes().decode("utf-8-sig")
    terminador = "\r\n" if "\r\n" in raw else "\n"
    rd = csv.DictReader(io.StringIO(raw, newline=""), delimiter=";")
    return list(rd.fieldnames or []), list(rd), terminador


def salvar_planilha(path: Path, campos: list[str], linhas: list[dict], terminador: str) -> None:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=campos, delimiter=";", lineterminator=terminador)
    w.writeheader()
    w.writerows(linhas)
    tmp = Path(str(path) + ".tmp")
    tmp.write_bytes(("﻿" + buf.getvalue()).encode("utf-8"))
    tmp.replace(path)


def caminho_decisoes(path: Path) -> Path:
    path = Path(path)
    return path.with_name(path.stem + "_decisoes.csv")


def ler_decisoes(path: Path) -> dict[str, dict]:
    p = caminho_decisoes(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8-sig", newline="") as f:
        return {r["anotacao_id"]: r for r in csv.DictReader(f, delimiter=";")}


def salvar_decisoes(path: Path, decisoes: dict[str, dict]) -> None:
    p = caminho_decisoes(path)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_DECISAO, delimiter=";", lineterminator="\n")
        w.writeheader()
        for aid in sorted(decisoes):
            w.writerow({c: decisoes[aid].get(c, "") for c in CAMPOS_DECISAO})


def anotada(linha: dict) -> bool:
    return all(str(linha.get(c, "")).strip() for c in ("suporte_semantico", "pt_formal", "completude"))
