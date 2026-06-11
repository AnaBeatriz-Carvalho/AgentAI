"""CLI: classifica cada discurso do gabarito em UM rotulo da taxonomia, usando o
Mistral 7B local (LM Studio) — a "abordagem LLM" da comparacao da clausula (a).

Diferenca vs. o app: o app produz `tema_principal` em TEXTO LIVRE (ate 5 palavras) e um
`agenda_politica` de 14 itens; aqui o modelo e RESTRITO ao conjunto fechado de rotulos da
taxonomia consolidada, para ser comparavel ponto-a-ponto com o gabarito e os baselines.

Reaproveita a infraestrutura existente de chamada ao LM Studio (cliente OpenAI-compativel
de `src.config.settings`). Prompt de classificacao documentado e byte-estavel (montado a
partir de `taxonomia.json`). Temperatura baixa.

ATENCAO (honestidade metodologica): o LM Studio pode IGNORAR `seed` (nao-determinismo de
GPU). Este script registra temperatura/seed como CONFIGURACAO, nao garantia de
reprodutibilidade exata — declare isso na dissertacao. Veja eval/README.md.

Uso:
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\classificar_mistral.py
    .\\.venv\\Scripts\\python.exe scripts\\classificacao\\classificar_mistral.py --fonte gabarito --limite 5
"""

from __future__ import annotations

import argparse
import difflib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.classificacao._comum import (
    COL_ID,
    GABARITO_CSV,
    PRED_MISTRAL,
    SNAPSHOT_CSV,
    carregar_taxonomia,
    normalizar,
    rotulos,
)
from src.config.settings import get_env, get_local_llm_config

_CFG = get_local_llm_config()


def construir_prompt(taxonomia: dict) -> str:
    """Bloco de instrucoes byte-estavel; o resumo do discurso e anexado por chamada."""
    linhas = []
    for rot in rotulos(taxonomia):
        defin = taxonomia["macrocategorias"][rot]["definicao"]
        linhas.append(f"- {rot}: {defin}")
    catalogo = "\n".join(linhas)
    return f"""Voce e um classificador de discursos parlamentares do Senado Federal brasileiro.
Sua tarefa: ler o RESUMO de um discurso e atribuir EXATAMENTE UMA categoria tematica.

Categorias permitidas (escolha apenas 1, pelo ASSUNTO PRINCIPAL do discurso):
{catalogo}

Regras:
- Classifique pelo objetivo/contexto predominante, NAO por palavras isoladas.
- Se houver mais de um tema, escolha o predominante.
- Homenagens/efemerides/aberturas de sessao sem agenda de politica publica -> Outros.
- Responda APENAS com o nome EXATO de uma categoria da lista acima, sem nenhuma outra
  palavra, sem pontuacao, sem explicacao.

RESUMO DO DISCURSO:
"""


def _casar_rotulo(resposta: str, rotulos_validos: list[str]) -> tuple[str, bool]:
    """Mapeia a saida do modelo para um rotulo valido. Retorna (rotulo, casou).

    `casou=False` quando a resposta nao corresponde a nenhum rotulo da taxonomia: o
    fallback e "Outros", mas o caso fica MARCADO (coluna `fora_taxonomia`) para revisao
    humana, em vez de virar "Outros" silenciosamente.
    """
    resp_norm = normalizar(resposta).strip()
    # 1) match exato normalizado
    for rot in rotulos_validos:
        if normalizar(rot) == resp_norm:
            return rot, True
    # 2) o rotulo aparece contido na resposta (modelo adicionou texto extra)
    for rot in rotulos_validos:
        if normalizar(rot) in resp_norm:
            return rot, True
    # 3) tolerancia a variantes morfologicas proximas (ex.: "Politicas" vs "Politica"):
    #    melhor similaridade entre os 5 rotulos; os rotulos sao bem distintos entre si,
    #    entao um limiar alto evita confusao. Conta como casamento valido.
    melhor, melhor_ratio = None, 0.0
    for rot in rotulos_validos:
        ratio = difflib.SequenceMatcher(None, normalizar(rot), resp_norm).ratio()
        if ratio > melhor_ratio:
            melhor, melhor_ratio = rot, ratio
    if melhor is not None and melhor_ratio >= 0.85:
        return melhor, True
    # 4) sem casamento -> fallback "Outros", marcado como fora da taxonomia
    return "Outros", False


def classificar_um(client, prompt_base: str, resumo: str, rotulos_validos: list[str],
                   temperatura: float, seed) -> tuple[str, str, bool]:
    """Retorna (rotulo_casado, resposta_bruta, casou) para um resumo."""
    kwargs = {
        "model": _CFG["model"],
        "messages": [{"role": "user", "content": prompt_base + (resumo or "").strip()}],
        "temperature": temperatura,
    }
    if seed not in (None, ""):
        kwargs["seed"] = seed
    resp = client.chat.completions.create(**kwargs)
    bruta = (resp.choices[0].message.content or "").strip()
    rotulo, casou = _casar_rotulo(bruta, rotulos_validos)
    return rotulo, bruta, casou


def main() -> int:
    parser = argparse.ArgumentParser(description="Classificacao tematica pelo Mistral (LM Studio).")
    parser.add_argument("--fonte", choices=["gabarito", "snapshot"], default="gabarito",
                        help="De onde ler os discursos a classificar (default: gabarito, "
                             "cai no snapshot se o gabarito ainda nao existir).")
    parser.add_argument("--temperatura", type=float, default=None,
                        help="Default: env LLM_EVAL_TEMPERATURE ou 0.1.")
    parser.add_argument("--seed", type=str, default=None,
                        help="Default: env LLM_SEED ou 42 (pode ser ignorado pelo runtime).")
    parser.add_argument("--limite", type=int, default=None, help="Classifica so os N primeiros.")
    parser.add_argument("--saida", type=str, default=str(PRED_MISTRAL))
    args = parser.parse_args()

    from openai import OpenAI
    client = OpenAI(base_url=_CFG["base_url"], api_key=_CFG["api_key"])

    temperatura = args.temperatura if args.temperatura is not None else float(get_env("LLM_EVAL_TEMPERATURE", "0.1"))
    seed_str = args.seed if args.seed is not None else str(get_env("LLM_SEED", "42"))
    try:
        seed = int(seed_str)
    except (TypeError, ValueError):
        seed = seed_str

    fonte = GABARITO_CSV if (args.fonte == "gabarito" and GABARITO_CSV.exists()) else SNAPSHOT_CSV
    if not fonte.exists():
        raise SystemExit(f"Fonte de discursos nao encontrada: {fonte}")
    df = pd.read_csv(fonte, encoding="utf-8")
    if args.limite is not None:
        df = df.head(args.limite)

    tx = carregar_taxonomia()
    rots = rotulos(tx)
    prompt_base = construir_prompt(tx)

    print(f"Fonte: {fonte.name} | discursos: {len(df)} | modelo: {_CFG['model']}")
    print(f"temp: {temperatura} | seed: {seed} (pode ser ignorada pelo LM Studio)\n")

    registros = []
    for i, row in enumerate(df.itertuples(index=False), 1):
        rid = getattr(row, COL_ID)
        resumo = getattr(row, "Resumo", "") or ""
        try:
            rotulo, bruta, casou = classificar_um(client, prompt_base, resumo, rots, temperatura, seed)
            fora = 0 if casou else 1
        except Exception as e:
            rotulo, bruta, fora = "Outros", f"[ERRO] {e}", 1
            print(f"  [ERRO] {rid}: {e}")
        registros.append({
            COL_ID: rid, "pred_mistral": rotulo, "fora_taxonomia": fora, "resposta_bruta": bruta,
        })
        if i % 10 == 0 or i == len(df):
            print(f"  [{i}/{len(df)}] ...")
        time.sleep(0)  # ponto de cortesia para nao saturar o servidor local

    out = pd.DataFrame(registros)
    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(saida, index=False, encoding="utf-8-sig")

    n_fora = int(out["fora_taxonomia"].sum())
    print(f"\nPredicoes salvas: {saida}")
    print("Distribuicao das predicoes (Mistral):")
    for rot, cont in out["pred_mistral"].value_counts().items():
        print(f"  {rot}: {cont}")
    if n_fora:
        print(f"\n[REVISAR] {n_fora} resposta(s) FORA da taxonomia (fallback->Outros, "
              "fora_taxonomia=1). Inspecione 'resposta_bruta' nessas linhas.")
    else:
        print("\nTodas as respostas casaram com a taxonomia (fora_taxonomia=0).")
    print("Lembrete: seed pode nao ser deterministica neste runtime — declare na metodologia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
