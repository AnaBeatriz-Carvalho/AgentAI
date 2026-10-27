"""LLM-como-juiz para o SUPORTE SEMÂNTICO da avaliação de geração (sinal secundário).

Para cada linha de `anotacao_geracao.csv` (cega ao modelo), pede a um LLM que atribua a
nota de suporte semântico 1-4 do codebook, comparando a resposta com a evidência gold.
Grava `resultados/geracao/juiz_geracao.csv` (anotacao_id;suporte_juiz;justificativa).
A nota humana continua sendo a referência; o `metricas_geracao.py` reporta apenas a
concordância humano x juiz.

Recomendação de método: usar como juiz um modelo que NÃO esteja entre os 4 avaliados
(evita viés de autopreferência) e registrar nome/versão/quantização no artigo.

Uso (LM Studio com o modelo-juiz carregado):
    python scripts/juiz_geracao.py --modelo <nome-no-lm-studio>
    python scripts/juiz_geracao.py --modelo <nome> --base-url http://localhost:1234/v1
Retoma de onde parou: linhas já presentes em juiz_geracao.csv são puladas.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GDIR = ROOT / "resultados" / "geracao"

PROMPT_SISTEMA = """Você é um avaliador rigoroso de respostas geradas sobre discursos do Senado Federal.
Avalie SOMENTE o suporte semântico: se o conteúdo da resposta é sustentado pela evidência de referência (gold).
Ignore se as citações [D1], [D2] existem; isso não importa aqui.

Escala:
1 = Não sustentada: as afirmações centrais contradizem o gold ou são fabricadas; não responde ao pedido.
2 = Erro relevante: o núcleo contém erro material (atribuição errada, contagem ou fato fabricado, troca de sujeito).
3 = Correta no núcleo, com lacunas: acerta o essencial, mas tem imprecisões menores, omissões ou fica genérica.
4 = Integralmente sustentada: responde ao pedido e tudo o que afirma é sustentado pelo gold.
Regra de desempate entre 2 e 3: se a resposta afirma algo falso como verdade, é 2; se apenas deixa de dizer, é 3.
Em perguntas sem resposta no corpus, reconhecer a ausência sem inventar dados é 4; inventar a informação é 1 ou 2.

Responda APENAS com JSON: {"suporte": <1-4>, "justificativa": "<uma frase>"}"""


def montar_prompt(r: dict) -> str:
    return (
        f"Pergunta: {r['pergunta']}\n"
        f"Tipo: {r['tipo']} | Há resposta no corpus: {r['tem_resposta_no_corpus']}\n"
        f"Gold (nota): {r['gold_nota'] or '-'}\n"
        f"Gold (evidência): {r['gold_evidencia'] or '-'}\n\n"
        f"Resposta a avaliar:\n{r['resposta_gerada']}"
    )


def extrair_nota(texto: str) -> tuple[int | None, str]:
    m = re.search(r"\{.*\}", texto or "", re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            n = int(d.get("suporte"))
            if 1 <= n <= 4:
                return n, str(d.get("justificativa", "")).strip()
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    m = re.search(r"suporte\"?\s*[:=]\s*([1-4])", texto or "")
    return (int(m.group(1)), "") if m else (None, (texto or "")[:200])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True, help="nome do modelo-juiz no servidor")
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--api-key", default=None)
    ap.add_argument("--temperatura", type=float, default=0.0)
    args = ap.parse_args()

    from openai import OpenAI
    from src.config.settings import get_local_llm_config
    cfg = get_local_llm_config()
    client = OpenAI(base_url=args.base_url or cfg["base_url"], api_key=args.api_key or cfg["api_key"])

    with open(GDIR / "anotacao_geracao.csv", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))

    destino = GDIR / "juiz_geracao.csv"
    feitos = set()
    if destino.exists():
        with open(destino, encoding="utf-8-sig", newline="") as f:
            feitos = {r["anotacao_id"] for r in csv.DictReader(f, delimiter=";") if r.get("suporte_juiz")}
    novo = not destino.exists()
    with open(destino, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["anotacao_id", "suporte_juiz", "justificativa", "modelo_juiz"],
                           delimiter=";")
        if novo:
            w.writeheader()
        for i, r in enumerate(linhas, 1):
            if r["anotacao_id"] in feitos:
                continue
            t0 = time.time()
            resp = client.chat.completions.create(
                model=args.modelo, temperature=args.temperatura,
                messages=[{"role": "system", "content": PROMPT_SISTEMA},
                          {"role": "user", "content": montar_prompt(r)}],
            )
            nota, just = extrair_nota(resp.choices[0].message.content)
            w.writerow({"anotacao_id": r["anotacao_id"], "suporte_juiz": nota or "",
                        "justificativa": just, "modelo_juiz": args.modelo})
            f.flush()
            print(f"[{i}/{len(linhas)}] {r['anotacao_id']} -> {nota} ({time.time()-t0:.1f}s)")
    print(f"OK -> {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
