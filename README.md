# Análise de Atividades do Senado com LLM local: artefato e materiais de avaliação

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)

Este repositório reúne o material de reprodutibilidade de um artigo científico em avaliação. Ele contém dois blocos. O primeiro é um artefato de software que acessa dados legislativos abertos do Senado Federal (pronunciamentos e votações) por uma interface local. O segundo é o conjunto de dados, scripts e resultados que sustentam a avaliação comparativa de modelos de linguagem (LLMs) em três dimensões (classificação temática, qualidade factual e rastreabilidade de citações), além da verificação do processo de ETL sobre o corpus coletado.

Todo o processamento com LLM roda de forma local, por um servidor compatível com a API OpenAI (por exemplo, LM Studio). Não há dependência de serviços pagos ou de nuvem.

Espelho anônimo para revisão: https://anonymous.4open.science/r/AgentAI-5283/

---

## Conteúdo do repositório

- **Artefato:** aplicação em Streamlit que coleta discursos e votações da API de Dados Abertos do Senado, classifica temas, responde a perguntas em linguagem natural e cita as fontes usadas em cada resposta.
- **Materiais de avaliação:** corpus anotado (gabarito), scripts que produzem cada métrica e os resultados versionados em `resultados/`.

Os dados do Senado são públicos. Os nomes de parlamentares que aparecem no corpus e nos resultados são dados públicos, não identificam a autoria da pesquisa.

---

## Reprodução dos resultados

Os resultados versionados ficam em `resultados/`, organizados por dimensão avaliada. O corpus bruto (SQLite) fica fora do versionamento (ver *Dados*) e é regenerável pela coleta a partir da API pública.

### Dados

- **Corpus de discursos:** banco SQLite local, gerado por `scripts/coletar_corpus.py`. Fica fora do versionamento (`data/*.sqlite` no `.gitignore`) por tamanho e por ser regenerável. Reproduza-o antes das avaliações que dependem do corpus.
- **Gabarito de classificação:** `resultados/gabarito/anotacao_discursos.csv` (amostra estratificada para anotação) e `resultados/gabarito/anotacao_discursos_categorizado.csv` (rótulo humano por categoria). O manifesto `resultados/gabarito/anotacao_discursos.manifesto.json` registra a semente (42), o tamanho da amostra (180, sendo 18 por categoria em 10 categorias), a população elegível e o período do corpus, para amostragem reprodutível.

### Dimensão 1: verificação do ETL (4.1)

- **Script:** `scripts/verificar_etl.py`.
- **Módulos de apoio:** `src/data/db.py`, `src/data/data_processing.py`.
- **Saída versionada:** `resultados/etl/verificacao_etl.json` (completude dos campos essenciais, consistência de duplicatas, datas, UFs e vínculos, e reprodutibilidade da re-coleta).

### Dimensão 2: classificação temática (4.2)

Ordem de execução:

1. `scripts/coletar_corpus.py` materializa o corpus no SQLite.
2. `scripts/exportar_anotacao.py` gera a amostra estratificada para anotação (semente fixa e manifesto).
3. `scripts/classificar_llm.py` classifica os discursos do gabarito com cada LLM (persistência por modelo, para comparar vários modelos).
4. `scripts/metricas_classificacao.py` calcula, contra o rótulo humano, acurácia, precisão, revocação e F1 por categoria, macro-F1, weighted-F1, Kappa de Cohen, matriz de confusão e concordância entre modelos.

- **Módulos de apoio:** `src/eval/categorias.py` (categorias e baseline por palavra-chave), `src/eval/classificador_llm.py` (prompt few-shot), `src/eval/metricas.py` (cálculo das métricas).
- **Saídas versionadas** em `resultados/metricas/`: `comparativo_modelos.csv` (uma linha por classificador), `f1_por_categoria.csv` (categorias por modelo), `concordancia_entre_modelos.csv` (agreement e Kappa par a par) e `metricas_classificacao.json` (consolidado, com matrizes de confusão).

### Dimensão 3: qualidade factual (4.3)

- **Script:** `scripts/avaliar_factual.py`. Gera cenários cuja resposta de referência é computada de forma determinística do corpus, roda o agente real (`gerar_resposta_discurso`, de `src/ai/local_llm_handler.py`) e atribui um veredito automático preliminar por presença dos fatos-chave.
- **Saídas versionadas:** `resultados/factual/avaliacao_factual.csv` (com a coluna `veredito_revisado` em branco para revisão humana) e `resultados/factual/avaliacao_factual.resumo.json`.

### Dimensão 4: rastreabilidade de citações (4.4)

- **Script principal:** `scripts/avaliar_rastreabilidade_corpus.py`. Roda consultas pelo mesmo caminho do app, mede cobertura de citação e integridade referencial contra o corpus e sinaliza extrapolações (citações *dangling* e candidatos a incompatibilidade semântica).
- **Saídas versionadas:** `resultados/rastreabilidade/traces_rastreabilidade.jsonl` (traces brutos) e `resultados/rastreabilidade/metricas_rastreabilidade.json`.
- **Wrapper de linha de comando:** `scripts/avaliar_rastreabilidade.py`, que lê `logs/qa_trace.jsonl` e imprime as métricas. A lógica de cálculo fica em `src/utils/rastreabilidade.py`, reutilizada também pela interface.

**Nota conceitual (central para esta dimensão).** A integridade referencial verifica se o identificador citado (`[D1]`, `[V1]`) existe entre as fontes recuperadas e no corpus. Ela não verifica se a fonte sustenta semanticamente a afirmação do agente. Os dois eixos são distintos. Uma citação pode ser referencialmente íntegra (o identificador existe) e ainda assim não sustentar a asserção do ponto de vista semântico. A checagem semântica é heurística (sobreposição de termos entre a frase citante e o resumo da fonte), reportada à parte e fora da métrica de integridade.

---

## Testes

Os testes automatizados (`pytest`) cobrem processamento de dados, votações, LLM local, o subpacote RAG, as métricas de rastreabilidade, as métricas de classificação e utilidades.

```bash
pytest -v
```

---

## Funcionalidade de RAG semântico (presente no código)

O subpacote `src/rag/` implementa uma busca semântica opcional sobre os discursos. Esta seção descreve o que existe no código, sem afirmar seu papel na avaliação do artigo.

O fluxo recupera o texto integral do pronunciamento (`senado_texto.py`, com fallback para o `Resumo`), quebra em trechos com sobreposição (`chunker.py`), gera embeddings em português normalizados em CPU (`embedder.py`), indexa em FAISS (`vectorstore.py`, `IndexFlatIP` com metadados em parquet) e recupera os trechos mais similares para compor o contexto citável (`retriever.py`, `rag_chat.py`). O índice vetorial e o cache de modelos ficam fora do versionamento (`vectorstore/` no `.gitignore`).

O chat conversacional do artefato usa recuperação de fontes por palavra-chave. O modo RAG semântico é um caminho alternativo, opcional, disponível no código.

---

## Execução do artefato (opcional)

Esta seção é secundária. Não é necessária para inspecionar dados, scripts ou resultados de avaliação.

Pré-requisitos: Python 3.10+ e um servidor compatível com a API OpenAI rodando localmente (por exemplo, LM Studio, com um modelo instruído carregado no endpoint local).

```bash
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajuste endpoint e modelo do LLM local, se necessário
streamlit run src/app/app_streamlit.py
```

Parâmetros do LLM local e do RAG são definidos por variáveis de ambiente (ver `.env.example`). Não versione segredos: o `.env` está no `.gitignore`.

---

## Estrutura do projeto

```
.
├── src/
│   ├── app/           # interface Streamlit (app_streamlit.py) e painel de rastreabilidade
│   ├── data/          # coleta, processamento e persistência (db.py, data_processing.py, votacoes_handler.py)
│   ├── ai/            # LLM local: retrieval de fontes, citação e trace (local_llm_handler.py)
│   ├── eval/          # avaliação: categorias, classificador LLM e métricas
│   ├── rag/           # busca semântica opcional (FAISS)
│   ├── utils/         # utilidades, logging e núcleo das métricas de rastreabilidade
│   └── config/        # settings e constantes
├── scripts/           # coleta do corpus e scripts de avaliação por dimensão
├── resultados/        # saídas versionadas (etl, gabarito, metricas, factual, rastreabilidade)
├── tests/             # testes automatizados (pytest)
├── logs/              # traces de execução (qa_trace.jsonl versionado; *.log fora do versionamento)
├── requirements.txt
├── .env.example
└── README.md
```

---

## Contato

Informações de contato disponíveis na versão não anônima.
