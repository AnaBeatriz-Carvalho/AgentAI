# Avaliação comparativa de modelos (gerador)

Protocolo: **fixar tudo exceto o LLM gerador**. Mesmo corpus congelado, mesma
recuperação por palavra-chave, mesmas perguntas, mesmo prompt, temperatura baixa e
seed fixas. Qualquer variação medida é atribuível só ao modelo.

## Fluxo

```powershell
# 0. Congelar o corpus (uma vez; reuse em TODA a avaliação)
.\.venv\Scripts\python.exe scripts\congelar_corpus.py --inicio 20250505 --fim 20250516
#    -> eval\corpus_snapshot.csv  +  eval\corpus_snapshot_ids.txt
#    (ou: --from-csv caminho\discursos.csv, a partir de um export existente)

# 1. Editar eval\perguntas.json: 30-50 perguntas estratificadas (~20% "Sem resposta no corpus")

# 2. Para CADA modelo: carregar no LM Studio e rodar (nada mais muda no código)
.\.venv\Scripts\python.exe scripts\coletar_avaliacao.py --modelo mistral-7b-instruct --quant Q4_K_M
#    -> eval\coleta_<modelo>.csv  (cole/importe na aba "2. Coleta (bruta)" da planilha)
```

Troque o modelo no LM Studio e reexecute o passo 2 — o `--modelo`/`--quant` só
carimbam o CSV; o modelo efetivo também é lido do campo `model` da resposta.

## O que o CSV traz (constante `HEADER` em `src/utils/eval_logger.py`)

`run_id, modelo, quantizacao, pergunta_id, tipo, resposta_gerada, ids_recuperados,
ids_citados, citacoes_validas, total_citacoes, alucinacao, recusou_correto,
latencia_1tok_s, tokens_por_s, vram_gb, temperatura, seed, timestamp`

**Não** preenche suporte semântico, PT formal nem completude: são anotação humana
cega (aba 3 da planilha). Automatizá-las enviesaria o Kappa de Cohen.

## Decisão de método para o artigo: namespace de citação

As citações do AgentAI são **refs por consulta** (`D1..Dn`, reatribuídos a cada
pergunta sobre o subconjunto recuperado). Por isso o `corpus_ids` passado ao logger é
o conjunto de refs **recuperados naquela consulta**:

- **integridade referencial por linha** = `citacoes_validas / total_citacoes` =
  proporção de citações que apontam para uma fonte efetivamente recuperada;
- **alucinação** = citou um ref fora do conjunto recuperado (id inexistente).

`eval/corpus_snapshot_ids.txt` guarda os **códigos reais do Senado** do snapshot
(proveniência/versionamento), artefato distinto do namespace de citação.

Como narrar: a **integridade referencial valida o pipeline** (tende a saturar, pois a
recuperação é fixa entre modelos); a **comparação entre modelos** se apoia em
**suporte semântico** (anotação humana) e **taxa de alucinação**, que variam com o
gerador.

## Cobertura da heurística automática de alucinação (limite explícito)

A coluna `alucinacao` (automática) cobre **apenas um** dos dois tipos de erro de
citação:

- ✅ **Capturado**: "citou um ref **fora da janela de recuperação** da consulta" —
  o modelo citou `[Dk]` que não está entre os refs recuperados (id inexistente para
  aquela pergunta). É o que a heurística marca como `alucinacao = 1`.
- ❌ **NÃO capturado**: "citou um ref **que não sustenta a afirmação**" — erro de
  **atribuição semântica**: o `[Dk]` existe e foi recuperado, mas o trecho citado não
  embasa a frase. A heurística não tem como detectar isso (o id é válido).

Esse segundo caso é medido **só pela anotação manual de suporte semântico** (escala
1–4, aba 3 da planilha), justamente a métrica que **discrimina** os modelos. Ou seja:
`alucinacao` automática = integridade de *referência* (o id existe?); suporte
semântico humano = integridade de *conteúdo* (o id sustenta o que foi dito?).

## Observações da validação ponta a ponta (Mistral 7B, teste mínimo)

- **Latência / throughput plausíveis**: ~2,9–3,8 s até o 1º token; ~22–33 tokens/s.
- **Seed NÃO é determinística** neste runtime: a mesma pergunta com `seed=42` gerou
  respostas diferentes entre execuções. O código envia `seed` no payload, mas o
  LM Studio/llama.cpp não garante saída byte-idêntica (não-determinismo de
  GPU/paralelismo). Registrar `temperatura` e `seed` documenta a *configuração*, não
  reprodutibilidade exata — declare isso na metodologia.
- **Citações agrupadas escapam à extração**: o modelo às vezes desobedece o prompt e
  emite `[D1, D2, D5]` (vários ids num colchete) em vez de `[D1] [D2] [D5]`. O regex
  do projeto (intencionalmente) só captura um id por colchete, então essas citações
  são **subcontadas** (não viram falsa alucinação — apenas não entram em
  `total_citacoes`). Pendência conhecida; um normalizador `[D1, D2] → [D1] [D2]` antes
  de extrair recuperaria esses casos, se desejado.
