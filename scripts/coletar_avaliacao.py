"""CLI: roda o conjunto fixo de perguntas contra o modelo ATIVO no LM Studio e gera
o CSV de coleta (formato HEADER) para a planilha de avaliação comparativa de modelos.

Princípio da avaliação: fixar TUDO exceto o LLM gerador. Este script:
  - carrega o corpus CONGELADO (`eval/corpus_snapshot.csv` — não a API ao vivo);
  - usa a recuperação por palavra-chave existente (`_selecionar_fontes`, inalterada);
  - usa o MESMO prompt do chat (`_montar_prompt_qa`, byte-idêntico);
  - fixa temperatura baixa e seed e os registra em cada linha;
  - extrai os IDs citados com a lógica existente (`extrair_ids_citados`);
  - carimba o modelo retornado pelo LM Studio em cada linha;
  - mede latência até o 1º token e tokens/s.

Para comparar modelos: troque o modelo no LM Studio (e, se quiser, ajuste --modelo/--quant)
e reexecute. NENHUMA outra parte do código muda entre modelos.

Uso:
    python scripts/coletar_avaliacao.py
    python scripts/coletar_avaliacao.py --modelo mistral-7b-instruct --quant Q4_K_M --seed 42
    python scripts/coletar_avaliacao.py --perguntas eval/perguntas.json --saida eval/coleta_mistral.csv

NÃO preenche colunas de anotação humana (suporte semântico, PT formal, completude):
essas são anotação manual e cega (aba 3 da planilha).
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from src.ai.local_llm_handler import gerar_resposta_qa
from src.config.settings import get_env
from src.utils.rastreabilidade import extrair_ids_citados
from src.utils.eval_logger import EvalLogger

EVAL_DIR = ROOT / "eval"
SNAPSHOT_CSV = EVAL_DIR / "corpus_snapshot.csv"
PERGUNTAS_PADRAO = EVAL_DIR / "perguntas.json"


def _carregar_snapshot(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        raise SystemExit(
            f"Snapshot de corpus não encontrado: {caminho}\n"
            "Rode antes: python scripts/congelar_corpus.py --inicio YYYYMMDD --fim YYYYMMDD"
        )
    df = pd.read_csv(caminho)
    if "Data" in df.columns:
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df


def _carregar_perguntas(caminho: Path) -> list[dict]:
    if not caminho.exists():
        raise SystemExit(f"Arquivo de perguntas não encontrado: {caminho}")
    dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
    perguntas = dados.get("perguntas", []) if isinstance(dados, dict) else dados
    # Normaliza para chaves internas, aceitando os dois esquemas de nomes:
    #   texto|pergunta, tem_resposta_no_corpus|tem_resposta.
    norm: list[dict] = []
    for p in perguntas:
        if not isinstance(p, dict):
            continue
        pid = p.get("id")
        texto = p.get("texto") or p.get("pergunta")
        if not (pid and texto):
            continue
        norm.append({
            "id": pid,
            "texto": texto,
            "tipo": p.get("tipo", ""),
            "tem_resposta": p.get("tem_resposta_no_corpus") or p.get("tem_resposta", ""),
        })
    return norm


def _sanitizar(nome: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", nome).strip("_") or "modelo"


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta de avaliação comparativa de modelos.")
    parser.add_argument("--modelo", type=str, default=None,
                        help="Nome do modelo p/ carimbar (default: campo 'model' da resposta do LM Studio).")
    parser.add_argument("--quant", type=str, default=None,
                        help="Quantização (default: env LOCAL_LLM_MODEL_QUANT ou vazio).")
    parser.add_argument("--seed", type=str, default=None,
                        help="Seed fixa (default: env LLM_SEED ou 42).")
    parser.add_argument("--temperatura", type=float, default=None,
                        help="Temperatura fixa baixa (default: env LLM_EVAL_TEMPERATURE ou 0.1).")
    parser.add_argument("--perguntas", type=str, default=str(PERGUNTAS_PADRAO))
    parser.add_argument("--snapshot", type=str, default=str(SNAPSHOT_CSV))
    parser.add_argument("--saida", type=str, default=None,
                        help="CSV de saída (default: eval/coleta_<modelo>.csv).")
    parser.add_argument("--limite", type=int, default=None,
                        help="Roda só as N primeiras perguntas (teste mínimo).")
    parser.add_argument("--no-stream", action="store_true",
                        help="Desliga o streaming (não mede latência até o 1º token).")
    args = parser.parse_args()

    temperatura = args.temperatura if args.temperatura is not None else float(get_env("LLM_EVAL_TEMPERATURE", "0.1"))
    seed_str = args.seed if args.seed is not None else str(get_env("LLM_SEED", "42"))
    try:
        seed: int | str = int(seed_str)
    except (TypeError, ValueError):
        seed = seed_str
    quant = args.quant if args.quant is not None else (get_env("LOCAL_LLM_MODEL_QUANT", "") or "")
    modelo_stamp = args.modelo or get_env("LOCAL_LLM_MODEL", "modelo")

    df = _carregar_snapshot(Path(args.snapshot))
    perguntas = _carregar_perguntas(Path(args.perguntas))
    if not perguntas:
        raise SystemExit("Nenhuma pergunta válida no arquivo. Edite eval/perguntas.json.")
    if args.limite is not None:
        perguntas = perguntas[:args.limite]

    logger = EvalLogger(model=modelo_stamp, quant=quant, temperature=temperatura, seed=seed)
    stream = not args.no_stream

    print(f"Corpus congelado: {len(df)} discursos | perguntas: {len(perguntas)}")
    print(f"Modelo (carimbo inicial): {modelo_stamp} | quant: {quant or '-'} | "
          f"temp: {temperatura} | seed: {seed} | stream: {stream}\n")

    for i, p in enumerate(perguntas, 1):
        pid, texto = p["id"], p["texto"]
        tipo = p["tipo"]
        tem_resposta = p["tem_resposta"]

        timer = logger.start()
        try:
            res = gerar_resposta_qa(df, texto, temperature=temperatura, seed=seed,
                                    timer=timer, stream=stream)
            resposta_txt = res.resposta
            ids_recuperados = res.ids_recuperados
            tokens = res.tokens_gerados
            # Carimba o modelo realmente retornado pelo LM Studio, salvo override manual.
            if not args.modelo and res.modelo:
                logger.model = res.modelo
        except Exception as e:  # uma falha não derruba a coleta inteira
            print(f"  [ERRO] {pid}: {e}")
            resposta_txt = f"[ERRO_GERACAO] {e}"
            ids_recuperados = []
            tokens = None

        ids_citados = extrair_ids_citados(resposta_txt)
        # corpus_ids = refs válidos DESTA consulta (namespace de citação do projeto é
        # por consulta: D1..Dn). Citar fora disso = alucinação de id.
        corpus_ids = set(ids_recuperados)

        logger.record(
            pergunta_id=pid,
            tipo=tipo,
            resposta=resposta_txt,
            ids_recuperados=ids_recuperados,
            ids_citados=ids_citados,
            corpus_ids=corpus_ids,
            tem_resposta_no_corpus=tem_resposta,
            tokens_gerados=tokens,
            timer=timer,
        )
        print(f"  [{i}/{len(perguntas)}] {pid} ({tipo}) "
              f"recup={len(ids_recuperados)} citados={len(ids_citados)}")

    saida = Path(args.saida) if args.saida else (EVAL_DIR / f"coleta_{_sanitizar(logger.model)}.csv")
    saida.parent.mkdir(parents=True, exist_ok=True)
    logger.to_csv(str(saida))

    print(f"\nCSV gerado: {saida}")
    print(f"Sanity-check: {logger.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
