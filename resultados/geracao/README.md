# Avaliação de Geração (comparação de 4 modelos)

Bundle versionado da avaliação de geração reportada no capítulo de Resultados do artigo
(cláusulas **(b)** qualidade factual e **(c)** rastreabilidade da hipótese). Complementa
as demais dimensões em `resultados/etl/`, `resultados/metricas/` (classificação),
`resultados/factual/` e `resultados/rastreabilidade/`.

> **Estado (2026-08-29).** As **respostas dos 4 modelos** (colunas automáticas do
> `EvalLogger`) foram recuperadas do histórico e versionadas aqui. A **anotação humana**
> (suporte semântico, recusa, PT formal, completude) — que discrimina os modelos no artigo —
> **se perdeu** e será refeita. Ver `../../PLANO-GERACAO-ROTA2.md` no repo do artigo e o
> `manifesto.json` deste diretório.

## Conteúdo

| Arquivo | O que é |
|---|---|
| `perguntas.json` | 40 perguntas estratificadas (14 factual direta, 8 agregação, 6 comparação, 4 busca por tema, 8 sem resposta), com `gold_ids`. |
| `corpus_snapshot.csv` | Corpus congelado: 152 discursos, 2025-05-05 a 2025-05-16 (9 datas), sem texto integral. |
| `corpus_snapshot_ids.txt` | Códigos oficiais reais do Senado do snapshot (proveniência). |
| `coleta_<modelo>.csv` | Respostas + métricas automáticas por modelo (`;`-separado). 40 linhas cada. |
| `PROTOCOLO.md` | Protocolo original da coleta (fixar tudo exceto o LLM gerador). |
| `manifesto.json` | Proveniência, condição de execução, hardware, colunas e estado da anotação. |

## Modelos avaliados (quantização Q4_K_M, LM Studio)
Mistral 7B Instruct v0.3 · Qwen2.5 7B Instruct · Llama 3.1 8B Instruct · Gemma 2 9B Instruct.

## Condição
Temperatura 0,1; seed 42 no payload mas **não controlada** no runtime; recuperação por
**palavra-chave** sobre o corpus congelado (não o caminho FAISS denso do chat ao vivo);
hardware Ryzen 7 5700X / 32 GB / RTX 4060 Ti 8 GB.

## O que ainda falta (roteiro em `PLANO-GERACAO-ROTA2.md`)
1. **Codebook** de anotação (níveis 1–4 de suporte semântico com exemplos-âncora).
2. **Re-anotação cega** das 160 respostas + **teste-reteste** (Kappa intra-anotador) +
   cross-check **LLM-como-juiz**.
3. `scripts/metricas_geracao.py` que recomputa a tabela do artigo a partir de
   `coleta_*.csv` + a anotação.
4. **Coleta pelo caminho FAISS** para comparação keyword × denso.

## Reproduzir a coleta (palavra-chave)

> **Atenção — dependência ainda não consolidada na `developer-v3`.** O
> `scripts/coletar_avaliacao.py` importa `gerar_resposta_qa` (de
> `src/ai/local_llm_handler.py`) e `extrair_ids_citados` (de
> `src/utils/rastreabilidade.py`), que existem **apenas na branch
> `feature/eval-logging-modelos`**. Na `developer-v3` o handler expõe
> `gerar_resposta_discurso` / `responder_pergunta_usuario_local`. Portar esse ponto de
> entrada de QA (e o `extrair_ids_citados`) para a `developer-v3` é parte da **Fase 2** do
> plano; até lá, a re-coleta roda a partir da branch de eval. As coletas versionadas aqui
> **não dependem** desse porte — são o registro congelado.

Com o modelo carregado no LM Studio (após a consolidação da Fase 2):
```bash
python scripts/coletar_avaliacao.py \
  --perguntas resultados/geracao/perguntas.json \
  --snapshot resultados/geracao/corpus_snapshot.csv
```
As colunas de anotação humana **não** são preenchidas por este script (são anotação manual e cega).
