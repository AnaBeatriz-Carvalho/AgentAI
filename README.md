# AgentAI: dados do Senado com LLM local

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)

Aplicação que coleta discursos e votações da API de Dados Abertos do Senado Federal e permite
consultar esses dados em linguagem natural. As respostas são geradas por um LLM rodando na
própria máquina e sempre mostram de onde veio cada informação.

Não depende de API paga nem de serviço em nuvem: o modelo roda localmente, por um servidor
compatível com a API da OpenAI (por exemplo, o LM Studio).

## O que a aplicação faz

- **Discursos:** coleta os pronunciamentos do período escolhido, classifica cada um em um tema
  e mostra a distribuição por tema e a linha do tempo, com filtros por parlamentar, partido e
  palavra-chave.
- **Votações:** lista as votações do Plenário e permite fazer perguntas sobre uma votação específica.
- **Chat com citação de fontes:** cada resposta cita os documentos usados (`[D1]`, `[V1]`), e só
  é possível citar o que foi de fato recuperado para aquela pergunta.
- **Rastreabilidade:** uma aba mostra, para as perguntas feitas, se as citações existem entre as
  fontes recuperadas e se há citações sem origem.
- **Busca semântica (opcional):** o módulo `src/rag/` busca no texto integral dos discursos com
  embeddings em português e índice FAISS.

## Como rodar

Pré-requisitos: Python 3.10+ e um servidor local de LLM rodando (LM Studio com um modelo
instruído carregado, por exemplo o Mistral 7B Instruct).

```bash
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # ajuste o endereço e o modelo do LLM local
streamlit run src/app/app_streamlit.py
```

As configurações do LLM e da busca semântica ficam no `.env` (veja o `.env.example`).

Para baixar e guardar o corpus de discursos em SQLite:

```bash
python scripts/coletar_corpus.py --inicio 2025-05-05 --fim 2025-05-16
```

## Testes

```bash
pytest -v
```

Os testes rodam no GitHub Actions a cada push na `main`.

## Estrutura

```
src/
├── app/       interface Streamlit
├── ai/        LLM local: recuperação de fontes, geração com citação e trace
├── data/      coleta, tratamento e persistência dos dados do Senado
├── rag/       busca semântica opcional (embeddings + FAISS)
├── eval/      categorias temáticas usadas na classificação
├── utils/     utilidades, logging e métricas de rastreabilidade
└── config/    configurações e constantes
scripts/       coleta do corpus e leitura do trace de rastreabilidade
tests/         testes automatizados (pytest)
```

## Pesquisa

O AgentAI é o artefato da minha dissertação de mestrado em Computação Inteligente (UFS). A
avaliação usada na pesquisa (gabaritos de anotação, scripts de métricas, resultados e histórico)
fica no branch [`pesquisa`](../../tree/pesquisa) e na tag `avaliacao-dissertacao`, para manter
este branch só com a aplicação.
