"""Testes do recálculo da tabela de geração (scripts/metricas_geracao.py).

Usa anotação SINTÉTICA num diretório temporário; nunca toca em resultados/geracao/.
"""
import csv
import importlib.util
import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GDIR = ROOT / "resultados" / "geracao"

spec = importlib.util.spec_from_file_location("metricas_geracao", ROOT / "scripts" / "metricas_geracao.py")
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)


def test_kappa_identico_e_oposto():
    assert mg.kappa([1, 2, 3, 4], [1, 2, 3, 4]) == 1.0
    assert mg.kappa([1, 1, 2, 2], [2, 2, 1, 1]) < 0
    assert mg.kappa([1, 2, 3, 4], [1, 2, 3, 4], ponderado=True) == 1.0


def test_kappa_ponderado_penaliza_menos_vizinhos():
    a = [1, 2, 3, 4, 1, 2, 3, 4]
    perto = [2, 2, 3, 3, 1, 2, 4, 4]
    longe = [4, 2, 3, 1, 4, 2, 3, 1]
    assert mg.kappa(a, perto, ponderado=True) > mg.kappa(a, longe, ponderado=True)


def test_validar_anotacao_detecta_fora_da_faixa():
    linhas = [{"anotacao_id": "A1", "suporte_semantico": "5", "pt_formal": "3", "completude": "3",
               "recusa_correta": "n/a", "tem_resposta_no_corpus": "Sim"}]
    erros, _ = mg.validar_anotacao(linhas)
    assert any("suporte_semantico" in e for e in erros)


def _dir_sintetico(tmp_path: Path) -> Path:
    d = tmp_path / "geracao"
    shutil.copytree(GDIR, d, ignore=shutil.ignore_patterns("metricas_geracao.json",
                                                            "comparativo_geracao.csv",
                                                            "tabela_comparativo_modelos.tex"))
    rnd = random.Random(0)
    linhas = mg.ler_csv(d / "anotacao_geracao.csv")
    for r in linhas:
        r["suporte_semantico"] = str(rnd.randint(1, 4))
        r["pt_formal"] = str(rnd.randint(3, 5))
        r["completude"] = str(rnd.randint(2, 5))
        if r["tem_resposta_no_corpus"] == "Não":
            r["recusa_correta"] = str(rnd.randint(0, 1))
    with open(d / "anotacao_geracao.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    return d


def test_pipeline_completo_sintetico(tmp_path, monkeypatch):
    d = _dir_sintetico(tmp_path)
    monkeypatch.setattr("sys.argv", ["x", "--dir", str(d)])
    assert mg.main() == 0
    res = json.loads((d / "metricas_geracao.json").read_text(encoding="utf-8"))
    assert res["anotacao_completa"] is True
    assert set(res["humanas"]) == {s for s, _ in mg.ORDEM_MODELOS}
    assert sum(h["recusa_anotadas"] for h in res["humanas"].values()) == 32
    tex = (d / "tabela_comparativo_modelos.tex").read_text(encoding="utf-8")
    assert tex.count(r"\\") == 4 and "--" not in tex.split("\n", 2)[2]


def test_automaticas_batem_com_o_artigo():
    auto = mg.metricas_automaticas(mg.carregar_coletas(GDIR))
    esperado = {"mistralai/mistral-7b-instruct-v0.3": 29.6, "qwen2.5-7b-instruct-1m": 23.1,
                "meta-llama-3.1-8b-instruct": 29.6, "gemma-2-9b-it": 4.15}
    for m, tps in esperado.items():
        assert auto[m]["integridade_referencial"] == 1.0
        assert auto[m]["alucinacao_referencial"] == 0.0
        assert abs(auto[m]["tokens_por_s_mediana"] - tps) < 0.06
    assert auto["mistralai/mistral-7b-instruct-v0.3"]["recusa_proxy_automatico"] == 1
