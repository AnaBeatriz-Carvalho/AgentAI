# Handoff — Experimento de avaliação da classificação temática (cláusula (a))

> **Projeto:** AgentAI (PROCC/UFS) — dashboard + chatbot sobre dados abertos do Senado,
> LLM local (Mistral 7B Instruct v0.3 via LM Studio), Streamlit, DSR.
> **Escopo deste handoff:** a frente da hipótese ainda não executada — **acurácia da
> classificação temática do Mistral vs. baselines sem LLM, contra gabarito humano**.
> As cláusulas (b) coerência factual e (c) rastreabilidade já foram avaliadas em outra
> frente; a geração (40 perguntas × 4 modelos) também. Esta é a frente que faltava.

## Estado atual (o que esta sessão deixou pronto)

Branch: `feature/eval-classificacao-tematica`. Infra de código + protocolo prontos; falta
a **anotação humana do gabarito** e a **execução** (passos 2–5 abaixo).

```
eval/classificacao/
  taxonomia.json            # 5 rótulos (config única: definições + mapa Senado + keywords)
  protocolo_anotacao.md     # protocolo fixado a priori + desvio de nº de anotadores
  README.md                 # fluxo de execução do experimento
  gabarito_para_anotar.csv  # template gerado (152 linhas) p/ anotar 'tema_gold'
  .gitignore                # ignora preds/resultados regeneráveis (não o gabarito)
scripts/classificacao/
  _comum.py                 # taxonomia, normalização, classificador keyword
  preparar_gabarito.py      # gera o template a partir do snapshot          [TESTADO]
  classificar_mistral.py    # classificação restrita do Mistral (LM Studio)  [requer LM Studio]
  baseline_keyword.py       # Baseline 1                                      [TESTADO]
  baseline_tfidf.py         # Baseline 2 (TF-IDF + SVM/NB, CV)                [TESTADO p/ smoke]
  metricas.py               # métricas + IC bootstrap + confusão + erros      [TESTADO p/ smoke]
```

`requirements.txt`: adicionado `scikit-learn` (instalado na venv).

## Decisões de método tomadas nesta sessão (2026-06-10)

1. **Taxonomia consolidada em 5 rótulos** (decisão da autora): *Política e Instituições;
   Economia e Trabalho; Segurança e Justiça; Políticas Sociais e Setoriais; Outros.*
   Motivo: com 152 discursos, as 12 categorias finas do app deixariam a maioria das
   classes < 20 instâncias. Fusões documentadas em `taxonomia.json` (`origem_12`,
   `esquema_senado`). Reabertura de "Políticas Sociais e Setoriais" é condicional ao
   volume observado no gabarito.
2. **Anotador único** (decisão da autora, FINAL): a pesquisadora anota **integralmente**,
   como na frente de geração. **Desvio declarado** da proposta (Seção 3.6.2 previa dupla
   anotação + Kappa). O **Prof. Gilton NÃO participa da anotação** — a orientação só toma
   ciência do desvio na redação. Declarar como limitação; **não** reportar Kappa nem fingir
   dupla anotação.
3. **Regra de decisão das classes <20 fixada a priori** (`protocolo_anotacao.md` §2.1):
   todas ≥20 → mantém 5; uma em 15–19 → aceita com ressalva; qualquer <15 ou ≥2 classes
   <20 → consolida para 4. `checar_gabarito.py` emite o veredito após a anotação.

## Descobertas relevantes do código (corrigem o modelo mental do handoff original)

- A coluna `Tema` de `corpus_snapshot.csv` **não** é do Mistral — é a heurística de
  palavra-chave (`classificar_tema_local`), atribuída em `congelar_corpus.py`. Ou seja, o
  **Baseline 1 já existia** na prática. O Mistral, no app, só produz `tema_principal` em
  texto livre + um `agenda_politica` de 14 itens — nenhum restrito à taxonomia da
  avaliação. Por isso `classificar_mistral.py` cria uma **classificação restrita ao
  conjunto fechado de 5 rótulos** (prompt próprio, documentado e byte-estável), reusando o
  cliente LM Studio de `src/config/settings.py`.
- Distribuição do Baseline 1 (keyword) no snapshot: Política 58, Economia/Trabalho 46,
  Outros 28, Segurança 10, Sociais 10. **Sinal de risco**: Segurança e Sociais podem ficar
  < 20 no gabarito → registrar e, se preciso, consolidar mais (decisão pós-contagem).

## Próximos passos (execução)

1. `preparar_gabarito.py` (já rodado → `gabarito_para_anotar.csv`).
2. **Anotar** `tema_gold` (humano) → salvar `gabarito.csv`. Seguir `protocolo_anotacao.md`.
   Conferir cobertura ≥150 e idealmente ≥20/classe.
3. LM Studio com o Mistral carregado → `classificar_mistral.py`.
4. `baseline_keyword.py` + `baseline_tfidf.py`.
5. `metricas.py` → `resultados/` (resumo, por classe, confusão, diferenças, casos de erro).
6. Transpor `resultados/resumo_metricas.csv` para a tabela LaTeX; redigir a análise
   qualitativa a partir de `casos_erro.csv`.

## Restrições que não podem ser violadas

- Mistral por **replicabilidade**, não superioridade (troca só vira "trabalho futuro").
- **Seed pode ser ignorada** pelo LM Studio (temp 0.1) — declarar config, não determinismo.
- Diferenças modestas = modestas; **sem significância formal** (só ICs descritivos).
- Amostra de 152 e anotador único são **limitações declaradas**.
- Conclusões restritas ao recorte congelado (maio/2025).
- Nada de chamar a recuperação do sistema de "RAG" vetorial (é por palavra-chave) — não
  toca este experimento, mas vale para a redação.

## Verificação encenada (antes de commitar)

`preparar_gabarito.py` e `baseline_keyword.py` rodam no snapshot real. `baseline_tfidf.py`
e `metricas.py` foram validados num smoke-test com **gabarito sintético temporário** (já
removido — não há gold falso no repo). `classificar_mistral.py` ainda não foi executado
ponta a ponta (depende do LM Studio ligado). **Sem commit/push sem OK explícito.**
