# Avaliação da classificação temática — cláusula (a)

Experimento que mede a **acurácia da classificação temática** do Mistral 7B contra um
**gabarito ouro humano** e **dois baselines sem LLM** (palavra-chave e TF-IDF+linear).
Independente da frente de geração (40 perguntas × 4 modelos), que vive em `eval/` raiz.

> Princípio: corpus congelado (`eval/corpus_snapshot.csv`, 152 discursos, maio/2025),
> taxonomia fechada e documentada (`taxonomia.json`), métricas com IC por **bootstrap**
> e **sem** reivindicação de significância estatística formal.

## Decisões de método fixadas (ver `protocolo_anotacao.md`)

- **Taxonomia consolidada em 5 rótulos** (4 substantivos + Outros), ancorada no esquema
  oficial do Senado; fusões documentadas em `taxonomia.json`.
- **Anotador único** (a pesquisadora, integralmente) — **desvio declarado** da proposta
  (que previa dupla anotação + Kappa). O Prof. Gilton **não participa da anotação**; a
  orientação só toma ciência do desvio na redação. Declarar como limitação; não fingir
  dupla anotação nem reportar Kappa.
- **Regra de decisão das classes <20 fixada a priori** (ver `protocolo_anotacao.md` §2.1);
  `checar_gabarito.py` emite o veredito após a anotação.

## Fluxo

```powershell
# (ativar venv)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .\.venv\Scripts\Activate.ps1

# 1. Gerar o template do gabarito (uma vez) -> abre no Excel
.\.venv\Scripts\python.exe scripts\classificacao\preparar_gabarito.py
#    -> eval\classificacao\gabarito_para_anotar.csv

# 2. SMOKE-TEST do Mistral (5 discursos) ANTES de anotar (LM Studio ligado):
#    confirma que o modelo devolve rótulos DENTRO da taxonomia (flag fora_taxonomia)
.\.venv\Scripts\python.exe scripts\classificacao\classificar_mistral.py --fonte snapshot --limite 5

# 3. ANOTAÇÃO HUMANA: preencher a coluna 'tema_gold' (5 rótulos exatos),
#    salvar como eval\classificacao\gabarito.csv  (ver protocolo_anotacao.md)

# 4. Conferir o gabarito + veredito da regra de decisão das classes <20 (§2.1)
.\.venv\Scripts\python.exe scripts\classificacao\checar_gabarito.py

# 5. Predições do Mistral (LM Studio com o Mistral carregado)
.\.venv\Scripts\python.exe scripts\classificacao\classificar_mistral.py
#    -> eval\classificacao\pred_mistral.csv

# 6. Baseline 1 (palavra-chave) e Baseline 2 (TF-IDF + linear, CV sobre o gabarito)
.\.venv\Scripts\python.exe scripts\classificacao\baseline_keyword.py
.\.venv\Scripts\python.exe scripts\classificacao\baseline_tfidf.py

# 7. Métricas consolidadas + IC bootstrap + matriz de confusão + casos de erro
.\.venv\Scripts\python.exe scripts\classificacao\metricas.py
#    -> eval\classificacao\resultados\*.csv
```

Os passos 5–6 podem rodar em qualquer ordem após o gabarito; o passo 7 usa o que existir
(sistemas sem `pred_*.csv` são pulados). Procedimento detalhado e checklist de honestidade:
`PROCEDIMENTO_EXECUCAO.md`.

## Artefatos

| Arquivo | Papel |
|---|---|
| `taxonomia.json` | Fonte única dos 5 rótulos, definições, mapeamento ao Senado e keywords do Baseline 1 |
| `protocolo_anotacao.md` | Protocolo de anotação (fixado a priori) + desvio do nº de anotadores |
| `gabarito_para_anotar.csv` | Template para a anotação humana (preencher `tema_gold`) |
| `gabarito.csv` | **Gabarito ouro** (gerado pela anotação — não versionado até existir) |
| `scripts/classificacao/preparar_gabarito.py` | Gera o template a partir do snapshot |
| `scripts/classificacao/checar_gabarito.py` | Valida o gabarito + veredito da regra §2.1 |
| `scripts/classificacao/classificar_mistral.py` | Classificação restrita do Mistral (LM Studio) |
| `scripts/classificacao/baseline_keyword.py` | Baseline 1 (palavra-chave) |
| `scripts/classificacao/baseline_tfidf.py` | Baseline 2 (TF-IDF + SVM/NB, validação cruzada) |
| `scripts/classificacao/metricas.py` | Métricas, IC bootstrap, confusão, casos de erro |
| `resultados/resumo_metricas.csv` | Tabela 1-linha-por-sistema (transpor p/ LaTeX) |

## Saída de métricas (`resultados/`)

- `resumo_metricas.csv` — acurácia, precisão/revocação/F1 macro, F1 weighted, com **IC95
  bootstrap** de acurácia e F1-macro, por sistema.
- `por_classe_<sistema>.csv` — precisão/revocação/F1/suporte por rótulo.
- `confusao_<sistema>.csv` — matriz de confusão.
- `diferencas_bootstrap.csv` — IC95 **pareado** da diferença (Mistral − baseline);
  **descritivo, sem teste de significância**.
- `casos_erro.csv` — discursos em que algum sistema errou (análise qualitativa).

## Restrições metodológicas (não violar)

1. Mistral 7B é o modelo do artefato por **replicabilidade**, não superioridade.
2. **Seed pode ser ignorada** pelo LM Studio — registrar temperatura/seed é documentar a
   *configuração*, não reprodutibilidade exata.
3. Diferenças modestas são reportadas como modestas; **sem significância formal**.
4. Amostra de 152 e anotador único são **limitações declaradas**, não achados.
5. Conclusões restritas ao recorte congelado (maio/2025).
