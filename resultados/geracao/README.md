# Avaliação de Geração (comparação de 4 modelos)

Bundle versionado da avaliação de geração reportada no capítulo de Resultados do artigo
(cláusulas **(b)** qualidade factual e **(c)** rastreabilidade da hipótese). Complementa
as demais dimensões em `resultados/etl/`, `resultados/metricas/` (classificação),
`resultados/factual/` e `resultados/rastreabilidade/`.

> **Estado (2026-10-27).** As respostas dos 4 modelos estão versionadas. A anotação humana
> original se perdeu e está sendo refeita na planilha cega `anotacao_geracao.csv`. Os scripts
> de métricas, reteste, LLM-juiz e coleta FAISS estão prontos. Ver `PLANO-GERACAO-ROTA2.md` no
> repositório do artigo.

## Conteúdo

| Arquivo | O que é |
|---|---|
| `perguntas.json` | 40 perguntas estratificadas (14 factual direta, 8 agregação, 6 comparação, 4 busca por tema, 8 sem resposta), com `gold_ids`. |
| `corpus_snapshot.csv` | Corpus congelado: 152 discursos, 2025-05-05 a 2025-05-16 (9 datas), sem texto integral. |
| `corpus_snapshot_ids.txt` | Códigos oficiais reais do Senado do snapshot (proveniência). |
| `coleta_<modelo>.csv` | Respostas + métricas automáticas por modelo (`;`-separado). 40 linhas cada. |
| `PROTOCOLO.md` | Protocolo original da coleta (fixar tudo exceto o LLM gerador). |
| `manifesto.json` | Proveniência, condição de execução, hardware, colunas e estado da anotação. |
| `codebook_anotacao.md` | Guia de anotação: escalas 1–4 / 1–5, definições e exemplos-âncora. |
| `anotacao_geracao.csv` | **Planilha de anotação cega** (embaralhada, sem o modelo), a preencher. |
| `_chave_modelos.csv` | Chave `anotacao_id → modelo`. **Não abrir durante a anotação.** |
| `anotacao_geracao_reteste.csv` | Reanotação cega de 49 respostas (31%), estratificada por tipo. Preencher só 2 a 4 semanas depois da rodada 1. |
| `juiz_geracao.csv` | Notas do LLM-juiz (gerado por `scripts/juiz_geracao.py`). |
| `metricas_geracao.json`, `comparativo_geracao.csv`, `tabela_comparativo_modelos.tex` | Saídas de `scripts/metricas_geracao.py`. |

## Modelos avaliados (quantização Q4_K_M, LM Studio)
Mistral 7B Instruct v0.3 · Qwen2.5 7B Instruct · Llama 3.1 8B Instruct · Gemma 2 9B Instruct.

## Condição
Temperatura 0,1; seed 42 no payload mas **não controlada** no runtime; recuperação por
**palavra-chave** sobre o corpus congelado (não o caminho FAISS denso do chat ao vivo);
hardware Ryzen 7 5700X / 32 GB / RTX 4060 Ti 8 GB.

## Fluxo (Fase 1)

1. Ler `codebook_anotacao.md` e preencher `anotacao_geracao.csv` (colunas `suporte_semantico`,
   `recusa_correta`, `pt_formal`, `completude`, `observacao`) **sem** abrir `_chave_modelos.csv`.
2. Prévia a qualquer momento: `python scripts/metricas_geracao.py --parcial`.
3. LLM-juiz (modelo fora dos 4 avaliados, carregado no LM Studio):
   `python scripts/juiz_geracao.py --modelo <nome>`.
4. Após 2 a 4 semanas, preencher `anotacao_geracao_reteste.csv` sem consultar a rodada 1.
5. Tabela final: `python scripts/metricas_geracao.py` e copiar as linhas de
   `tabela_comparativo_modelos.tex` para o quadro `tab:comparativo_modelos` do artigo.

## Pendências

- [x] Codebook, planilha cega, planilha de reteste.
- [x] `scripts/metricas_geracao.py` (colunas automáticas conferidas com o artigo).
- [x] `scripts/juiz_geracao.py`.
- [x] Porte de `gerar_resposta_qa` e coleta com `--recuperador faiss`.
- [ ] Anotação das 160 respostas, reteste e execução do juiz.
- [ ] Coleta FAISS dos 4 modelos e sua anotação (comparação palavra-chave x denso).

## Coleta (palavra-chave ou FAISS)

Com o modelo carregado no LM Studio, repita para cada um dos 4 modelos:
```bash
python scripts/coletar_avaliacao.py --recuperador faiss --modelo <stamp> --quant Q4_K_M
```
Saídas: `faiss/coleta_<modelo>.csv` ou `recoleta_palavra_chave/coleta_<modelo>.csv`. As coletas
congeladas desta pasta nunca são sobrescritas. A busca densa indexa em memória os 152 registros
do snapshot com o embedder de `RAG_EMBEDDING_MODEL` e usa o mesmo k (15) e o mesmo prompt.
As colunas de anotação humana não são preenchidas pela coleta.
