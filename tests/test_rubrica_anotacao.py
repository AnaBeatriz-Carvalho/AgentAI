"""Testes da rubrica guiada e da gravação da planilha de anotação."""
import shutil
from pathlib import Path

import pytest

from src.eval import rubrica_anotacao as rb

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("acerto,erro,sobra,esperado", [
    ("completo", "nao", None, 4),
    ("parcial", "nao", None, 3),
    ("nao", "nao", None, 3),          # genérica sem afirmar nada falso (âncora Q04, nota 3)
    ("completo", "secundario", None, 3),
    ("parcial", "principal", "sim", 2),  # âncora Q04, nota 2
    ("nao", "principal", "nao", 1),
])
def test_suporte_com_resposta(acerto, erro, sobra, esperado):
    d = rb.derivar("Sim", acerto, erro, sobra)
    assert d.suporte == esperado and d.recusa == "n/a"


def test_sem_resposta_recusa_e_suporte():
    assert (rb.derivar("Não", "completo", "nao").suporte, rb.derivar("Não", "completo", "nao").recusa) == (4, "1")
    assert rb.derivar("Não", "parcial", "secundario").recusa == "1"
    d = rb.derivar("Não", "nao", "principal", "nao")
    assert (d.suporte, d.recusa) == (1, "0")


def test_inconsistencia_sinalizada():
    d = rb.derivar("Não", "nao", "nao")
    assert d.suporte is None and d.aviso


def test_principal_exige_sobra():
    assert rb.derivar("Sim", "parcial", "principal").suporte is None


def test_salvar_preserva_demais_colunas(tmp_path):
    origem = ROOT / "resultados" / "geracao" / "anotacao_geracao.csv"
    p = tmp_path / "a.csv"
    shutil.copy(origem, p)
    campos, linhas, term = rb.ler_planilha(p)
    antes = [dict(r) for r in linhas]
    linhas[0]["suporte_semantico"] = "3"
    rb.salvar_planilha(p, campos, linhas, term)
    _, depois, term2 = rb.ler_planilha(p)
    assert term2 == term and len(depois) == len(antes)
    for a, b in zip(antes, depois):
        for c in campos:
            if c not in rb.NOTAS:
                assert a[c] == b[c]
    assert depois[0]["suporte_semantico"] == "3"


def test_salvar_sem_alterar_e_byte_identico(tmp_path):
    origem = ROOT / "resultados" / "geracao" / "anotacao_geracao.csv"
    p = tmp_path / "a.csv"
    shutil.copy(origem, p)
    campos, linhas, term = rb.ler_planilha(p)
    rb.salvar_planilha(p, campos, linhas, term)
    assert p.read_bytes() == origem.read_bytes()
