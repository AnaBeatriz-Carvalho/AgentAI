# Avaliação de Geração (comparação de 4 modelos)

Bundle versionado da avaliação de geração reportada no capítulo de Resultados do artigo
(cláusulas **(b)** qualidade factual e **(c)** rastreabilidade da hipótese). Complementa
as demais dimensões em `resultados/etl/`, `resultados/metricas/` (classificação),
`resultados/factual/` e `resultados/rastreabilidade/`.

> **Estado (2026-11-04).** Anotação humana das 160 respostas concluída (rodada 1, 27/10/2026),
> com revisões pontuais registradas no histórico abaixo. Reteste intra-anotador concluído
> (49 respostas, 04/11/2026). LLM-juiz executado. Pendente: anotação da coleta FAISS. Ver a
> seção **Histórico** e `PLANO-GERACAO-ROTA2.md` no repositório do artigo.

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
| `anotacao_geracao.csv` | **Planilha de anotação cega** (embaralhada, sem o modelo), rodada 1 preenchida. |
| `anotacao_geracao_decisoes.csv` | Caminho de decisão da rubrica (acerto, erro, sobra) de cada item da rodada 1. |
| `_chave_modelos.csv` | Chave `anotacao_id → modelo`. **Não abrir durante a anotação.** |
| `anotacao_geracao_reteste.csv` | Reanotação cega de 49 respostas (31%), estratificada por tipo. Preenchida em 04/11/2026 (ver desvio de prazo no histórico). |
| `anotacao_geracao_reteste_decisoes.csv` | Caminho de decisão da rubrica de cada item do reteste. |
| `juiz_geracao.csv` | Notas do LLM-juiz (gerado por `scripts/juiz_geracao.py`). |
| `metricas_geracao.json`, `comparativo_geracao.csv`, `tabela_comparativo_modelos.tex` | Saídas de `scripts/metricas_geracao.py`. |

## Modelos avaliados (quantização Q4_K_M, LM Studio)
Mistral 7B Instruct v0.3 · Qwen2.5 7B Instruct · Llama 3.1 8B Instruct · Gemma 2 9B Instruct.

## Condição
Temperatura 0,1; seed 42 no payload mas **não controlada** no runtime; recuperação por
**palavra-chave** sobre o corpus congelado (não o caminho FAISS denso do chat ao vivo);
hardware Ryzen 7 5700X / 32 GB / RTX 4060 Ti 8 GB.

## Fluxo (Fase 1)

1. Anotar pela interface guiada: `streamlit run scripts/anotar_geracao.py` (ver a seção 9 do
   codebook). Ela grava em `anotacao_geracao.csv` e registra o caminho de decisão em
   `anotacao_geracao_decisoes.csv`. Não abrir `_chave_modelos.csv`, `juiz_geracao.csv` nem `faiss/`.
2. Prévia a qualquer momento: `python scripts/metricas_geracao.py --parcial`.
3. LLM-juiz (modelo fora dos 4 avaliados, carregado no LM Studio):
   `python scripts/juiz_geracao.py --modelo <nome>`.
4. Após 2 a 4 semanas, reanotar pela mesma interface:
   `streamlit run scripts/anotar_geracao.py -- --arquivo resultados/geracao/anotacao_geracao_reteste.csv`.
5. Tabela final: `python scripts/metricas_geracao.py` e copiar as linhas de
   `tabela_comparativo_modelos.tex` para o quadro `tab:comparativo_modelos` do artigo.

## Pendências

- [x] Codebook, planilha cega, planilha de reteste.
- [x] `scripts/metricas_geracao.py` (colunas automáticas conferidas com o artigo).
- [x] `scripts/juiz_geracao.py`.
- [x] Porte de `gerar_resposta_qa` e coleta com `--recuperador faiss`.
- [x] Anotação das 160 respostas (27/10/2026), reteste (04/11/2026) e execução do juiz.
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

## Histórico

Registro cronológico do que foi feito na avaliação de geração. Os commits citados estão no
`main` do repositório.

| Data | O que foi feito | Commit |
|---|---|---|
| 29/08/2026 | Bundle da avaliação versionado (Fase 0); codebook e planilha cega (Fase 1). | `d1b1fe8`, `93d228d` |
| 27/10/2026 | Scripts de métricas, reteste, LLM-juiz e coleta FAISS; notas do LLM-juiz e coletas FAISS dos 4 modelos. | `f39f782`, `53f6d9e` |
| 27/10/2026 | Interface de anotação guiada por rubrica de decisão (acerto, erro, sobra). | `b2873e3` |
| 27/10/2026 | Rodada 1: anotação humana cega das 160 respostas (17:55 a 20:30), refeita porque a planilha original se perdeu. | `0b4424c` |
| 27/10/2026 | Revisão dos itens da âncora Q04 (A028, A051) e errata do codebook. | `db3ab8b` |
| 29/10/2026 | Revisão do item A034 (Q04): suporte 1 → 3, completude 1 → 4. | `c01f50d` |
| 04/11/2026 | Métricas recalculadas após a revisão do A034. Gemma 2 9B: suporte 3,15 → 3,20; completude 3,38 → 3,45. Na Q04 os 4 modelos passam a ter suporte 3,0. | `f788182` |
| 04/11/2026 | Reteste intra-anotador: 49 respostas reanotadas às cegas (11:13 a 12:47). | `3094290` |
| 04/11/2026 | Métricas recalculadas com o reteste. Suporte semântico (n = 49): concordância exata 0,551; ±1 0,837; kappa 0,311; kappa ponderado quadrático 0,598. | `b52f8b8` |

### Desvio de protocolo

O protocolo previa o reteste de 2 a 4 semanas após a rodada 1. O reteste foi feito **8 dias**
depois (27/10 → 04/11/2026), **por restrição de cronograma da dissertação**. Para reduzir o risco
de a anotadora lembrar as notas, foram mantidas a anotação cega (sem identificação do modelo) e
a ordem de apresentação distinta da rodada 1, sobre um volume de 160 itens. O intervalo real
deve ser informado no texto.

### Observações do reteste

- A nota 4 é estável (21 de 24 itens repetidos); a oscilação se concentra entre 1 e 3.
- Nos 22 itens divergentes, o julgamento de **erro** mudou em 14 e o de **acerto** em 9. A
  **sobra** mudou em 15, quase sempre como consequência do caminho de erro (só 3 casos sem
  mudança de erro). Todos os saltos de 2 pontos (3 ↔ 1) vieram de alternância entre "sem erro"
  e "erro principal".
- Concordância exata por tipo: factual direta 6/17, busca por tema 2/5, comparação 5/7,
  agregação/contagem 7/10, sem resposta no corpus 7/10.
- A diferença de suporte entre os modelos (2,98 a 3,23) é menor que a variação intra-anotadora.

