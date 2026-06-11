# Classificação temática (cláusula (a)) — procedimento de execução dos testes

> AgentAI (PROCC/UFS). Avaliação da acurácia da classificação temática do Mistral 7B
> contra gabarito ouro humano e dois baselines sem LLM (palavra-chave e TF-IDF+linear),
> sobre o corpus congelado de 152 discursos do Senado (maio/2025).
>
> Este é o **procedimento de execução**. O texto para o artigo (método, taxonomia,
> limitações) está no repositório do artigo.

---

## 0. Pré-requisitos

- Branch `feature/eval-classificacao-tematica` (já criada).
- `scikit-learn` instalado e registrado em `requirements.txt` (feito).
- Corpus congelado em `eval/corpus_snapshot.csv` (152 discursos).
- Scripts em `scripts/classificacao/` e config em `eval/classificacao/`.
- LM Studio com o Mistral 7B Instruct v0.3 carregado (só para a etapa do Mistral).

## 1. Sequência de execução (ordem importa)

A ordem evita retrabalho: trava-se a taxonomia e o protocolo, valida-se o encanamento, só
então se anota o gabarito inteiro (a etapa cara e irreversível em esforço humano).

1. **Fixar a regra de decisão das classes <20 e o protocolo de anotação** (Seção 2) —
   ANTES de anotar qualquer item.
2. **Smoke-test real do Mistral (5 discursos)** (Seção 3) — antes de anotar, para flagrar
   bug de parsing de rótulo cedo.
3. **Anotar o gabarito** (Seção 4): preencher `tema_gold` nos 152 itens do template.
4. **Aplicar a regra de decisão** sobre a contagem real do gabarito (Seção 2) e registrar o
   resultado (manter 5 rótulos ou consolidar). Use `checar_gabarito.py`.
5. **Rodar as três abordagens** (Seção 5): Mistral, Baseline 1, Baseline 2.
6. **Rodar as métricas** (Seção 6): tabelas, IC bootstrap, matriz de confusão, export de erros.
7. **Transpor os números** para o texto do artigo (contagem por classe; tabela de resultados).

## 2. Regra de decisão das classes pouco povoadas (fixar antes de anotar)

Defina o gatilho por escrito agora, para não parecer ajuste posterior. Apenas o ramo acionado
é registrado depois da contagem (`checar_gabarito.py` imprime o veredito):

- Anotar os 152 nos 5 rótulos.
- Se **toda** classe alcançar ≥20 → mantém 5 rótulos.
- Se **uma** classe ficar em 15–19 → aceita, reporta a métrica por classe dessa categoria com
  ressalva explícita de instabilidade (n baixo) e enfatiza macro/ponderada.
- Se **qualquer** classe ficar <15, ou **duas ou mais** ficarem <20 → consolida para 4
  rótulos. A fusão segue o mesmo critério da taxonomia: ancorada no esquema do Senado e
  documentada (candidata mais provável: agrupar a menor classe na macrocategoria afim).

## 3. Smoke-test real do Mistral (antes de anotar)

O smoke-test anterior usou gabarito sintético que era a saída do keyword — testou só o
encanamento (deu keyword=1.000, tautológico). Falta exercitar `classificar_mistral.py` contra
o LM Studio ligado, ao menos em 5 itens, para confirmar que o modelo devolve rótulos DENTRO da
taxonomia fechada (e que o parsing trata bem respostas fora do conjunto).

- Subir o LM Studio com o Mistral carregado.
- `classificar_mistral.py --fonte snapshot --limite 5`.
- Conferir: todo rótulo devolvido pertence aos 5 da taxonomia? A coluna `fora_taxonomia`
  marca (=1) respostas fora do conjunto (fallback → "Outros") para revisão.
- Registrar a condição real de inferência (temperatura; semente não controlada).

## 4. Anotação do gabarito

- O template `gabarito_para_anotar.csv` (152 linhas) já existe; `tema_gold` nasce vazio de
  propósito — confirmar isso antes de começar.
- **Anotação cega:** o arquivo NÃO contém predição de nenhum sistema (keyword/Mistral), para
  não enviesar o gabarito contra os sistemas que ele julga.
- Anotar lendo o `Resumo`, seguindo as definições e regras de desempate do protocolo.
- Salvar como `gabarito.csv` (este SIM é versionado; é o gabarito ouro).

## 5. Rodar as três abordagens

Com `gabarito.csv` preenchido:

- **Baseline 1 (keyword):** determinístico, independente do gabarito; gera `pred_keyword.csv`.
- **Baseline 2 (TF-IDF+linear):** validação cruzada estratificada sobre o gabarito
  (predição out-of-fold, comparável ponto a ponto); gera `pred_tfidf.csv`.
- **Mistral:** classificação restrita aos 5 rótulos sobre os 152; gera `pred_mistral.csv`.
  Requer LM Studio ligado.

## 6. Métricas e saída final

- `metricas.py`: acurácia/precisão/revocação/F1 por classe e macro/ponderada, para as três
  abordagens; IC por bootstrap para acurácia e F1-macro; IC bootstrap pareado da diferença
  (Mistral − baseline), descritivo, sem significância; matriz de confusão por abordagem;
  export dos casos de erro para a análise qualitativa.
- Transpor a tabela consolidada para o LaTeX e preencher a contagem por classe e a tabela de
  resultados no texto do artigo.

## 7. Checklist de honestidade antes de fechar

- [ ] Anotador único declarado como desvio, sem fingir dupla anotação/Kappa.
- [ ] Regra de decisão das classes <20 fixada ANTES da anotação; ramo acionado registrado depois.
- [ ] Condição real de semente declarada (não determinismo).
- [ ] IC da diferença interpretado de forma descritiva; se cruza zero, dito explicitamente.
- [ ] Nenhuma recomendação de trocar o Mistral no corpo do texto (no máximo, trabalho futuro).
- [ ] Conclusões restritas ao recorte de maio/2025.

> Anotação feita integralmente pela pesquisadora (anotadora única). O Prof. Gilton não
> participa de nenhum trabalho de anotação. A condição de anotador único é declarada como
> desvio no texto do artigo; a orientação apenas toma ciência do desvio na redação, sem
> envolvimento operacional.
