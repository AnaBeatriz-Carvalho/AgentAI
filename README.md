# 🏛️ Análise de Atividades do Senado (LLM Local + Streamlit)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)

Aplicação web interativa para analisar **pronunciamentos (discursos)** e **votações** do Senado Federal (dados públicos), com:

- **LLM local** para classificação/análise de discursos e chat com os dados (via API OpenAI-compatível, ex.: LM Studio)

---

## 🚀 Funcionalidades

- **🗣️ Discursos:** coleta por período, classificação temática, resumo e atributos (agenda, tom, posicionamento etc.)
- **📊 Dashboard:** gráficos (Plotly) e tabela filtrável
- **💬 Chat com os dados:** perguntas em linguagem natural sobre discursos e votações, com retrieval por palavra-chave (RAG simplificado sobre DataFrame Pandas) seguido de geração
- **🗳️ Votações:** exploração por período, filtros por partido/parlamentar e export CSV
- **🔎 Rastreabilidade:** cada resposta do chat cita as fontes que a fundamentaram (`[D1]`, `[V1]`…), expõe a tabela de discursos/votos usados e grava um *trace* por consulta para auditoria
- **📈 Painel de rastreabilidade:** aba dedicada na interface com métricas de cobertura/precisão de citação (geral e por origem), sem precisar do terminal

---

## ⚙️ Tecnologias

| Categoria | Ferramenta |
|---|---|
| Linguagem | Python 3.10+ |
| App web | Streamlit |
| Dados | Pandas |
| Visualização | Plotly |
| HTTP | Requests |
| LLM local | OpenAI SDK apontando para servidor local (ex.: LM Studio) |
| Testes | Pytest |
| Config | python-dotenv |

---

## 🧩 Estrutura do Projeto  

```
AgentAI/
│
├── src/
│   ├── app/
│   │   └── app_streamlit.py      # Interface principal (Streamlit) + aba de rastreabilidade
│   ├── data/
│   │   ├── data_processing.py    # Processamento de discursos (+ id_discurso estável)
│   │   └── votacoes_handler.py   # Extração e organização das votações
│   ├── ai/
│   │   └── local_llm_handler.py  # LLM local: retrieval de fontes, citação e trace de QA
│   ├── utils/
│   │   ├── helpers.py            # Funções auxiliares gerais
│   │   ├── logger.py             # Logging centralizado
│   │   └── rastreabilidade.py    # Núcleo das métricas de rastreabilidade
│   └── config/
│       ├── settings.py           # Carregamento de variáveis de ambiente
│       └── constants.py          # Constantes (ids, guardrails de contexto do prompt)
│
├── scripts/
│   └── avaliar_rastreabilidade.py # CLI: lê logs/qa_trace.jsonl e imprime as métricas
│
├── tests/                        # Testes automatizados com pytest
│   ├── test_data_processing.py   # Testes de processamento de dados (+ id_discurso)
│   ├── test_votacoes_handler.py  # Testes de votações
│   ├── test_local_llm_handler.py # Testes do LLM local (retrieval + trace)
│   ├── test_avaliar_rastreabilidade.py # Testes das métricas de rastreabilidade
│   ├── test_utils_helpers.py     # Testes de utilidades
│   ├── test_plotly_export.py     # Testes de visualização
│   └── conftest.py               # Configurações pytest
│
├── logs/                         # Logs de execução (qa_trace.jsonl gerado pelo chat)
├── run_app.py                    # Script auxiliar para iniciar a aplicação
├── inspect_votacoes.py           # Script para inspecionar dados de votações
├── inspect_periodo_votacoes.py   # Script para análise de períodos de votação
├── requirements.txt              # Dependências do projeto
├── .env.example                  # Exemplo de variáveis de ambiente (NÃO comite chaves reais)
├── .env                          # Variáveis locais (NÃO comite)
├── .gitignore                    # Arquivos a ignorar no git
├── README.md                     # Este arquivo
```

---

## 💻 Instalação e Execução

### Pré-requisitos
- Python 3.10+
- Um servidor **OpenAI-compatível** rodando localmente para o LLM (recomendado: **LM Studio**)

---

### Passos

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/AnaBeatriz-Carvalho/AgentAI.git
   cd AgentAI
   ```

2. **Crie e ative o ambiente virtual:**
   ```bash
   python -m venv venv
   # Linux/Mac
   source venv/bin/activate
   # Windows
   .\venv\Scripts\activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as variáveis de ambiente (opcional, mas recomendado):**

    - Copie o arquivo de exemplo:
       ```bash
       cp .env.example .env
       ```
    - Se quiser alterar endpoint/modelo do LLM local, edite no `.env`:
       ```
       LOCAL_LLM_BASE_URL="http://localhost:1234/v1"
       LOCAL_LLM_API_KEY="lm-studio"
       LOCAL_LLM_MODEL="mistralai/mistral-7b-instruct-v0.3"
       ```
    - **Nota:** Se o servidor LLM estiver em outra máquina, substitua `localhost` pelo IP específico (ex.: `http://192.168.x.x:1234/v1`)

5. **Inicie o LLM local (LM Studio):**

   - Abra o LM Studio
   - Carregue o modelo **Mistral 7B Instruct** (recomendado: `mistralai/mistral-7b-instruct-v0.3`) e inicie o **Local Server** no endpoint `http://localhost:1234/v1`
   - O projeto está configurado para usar este modelo por padrão (ajuste via `.env` se necessário)

6. **Execute a aplicação:**
   ```bash
   streamlit run src/app/app_streamlit.py
   ```

   Alternativa:
   ```bash
   python run_app.py
   ```

7. **Acesse no navegador:**
   [http://localhost:8501](http://localhost:8501)

---

## 🔧 Configuração do tema (Streamlit)

Existe um arquivo de tema em `streamlit/config.toml`. O Streamlit normalmente lê esse arquivo a partir de `.streamlit/config.toml`.

Se você quiser garantir que o tema seja aplicado:

```bash
mkdir -p .streamlit
cp streamlit/config.toml .streamlit/config.toml
```

Importante: não deixe chaves/segredos dentro desse TOML.

---

## 🧪 Executando Testes  

O projeto inclui **testes automatizados** com `pytest` para garantir qualidade e confiabilidade.  

Execute todos os testes:
```bash
pytest -v
```

Teste específico:
```bash
pytest tests/test_local_llm_handler.py -v
```

Cobertura de testes:
```bash
pytest --cov=src tests/
```

**Testes disponíveis:**
- `test_data_processing.py` — Extração e processamento de discursos (inclui `id_discurso`)
- `test_votacoes_handler.py` — Manipulação de dados de votações
- `test_local_llm_handler.py` — Análise/classificação com LLM, retrieval de fontes e trace
- `test_avaliar_rastreabilidade.py` — Métricas de rastreabilidade
- `test_utils_helpers.py` — Funções auxiliares
- `test_plotly_export.py` — Visualizações e gráficos

---

## 🔎 Rastreabilidade

O chat foi instrumentado para vincular cada resposta às fontes que a fundamentaram (resposta → registro):

- **Fontes citáveis:** a cada consulta os discursos/votos recuperados recebem um id curto (`D1..Dn`, `V1..Vn`); o modelo é instruído a citar **só** esses ids (`[D1] [D3]`). O código real do Senado fica visível na tabela de fontes e é gravado para auditoria.
- **Retrieval por palavra-chave:** `_selecionar_fontes` filtra a base (Resumo/Parlamentar/Tema/Partido) pelos termos da pergunta, com *fallback* para uma amostra geral, e só esse subconjunto vai ao prompt (respeitando guardrails de contexto — `MAX_FONTES_PROMPT` / `MAX_CHARS_CONTEXTO_PROMPT`).
- **Fontes na interface:** cada resposta traz um `expander` "📚 Fontes utilizadas" com a tabela dos registros usados.
- **Trace por consulta:** uma linha JSON por pergunta é gravada em `logs/qa_trace.jsonl` (`timestamp`, `pergunta`, `fontes_ids`, `fontes_codigos`, `n_fontes`, `resposta`, `origem`).
- **Métricas:** cobertura de recuperação, cobertura de citação e precisão de citação — visíveis na aba **📊 Rastreabilidade** da interface ou via terminal:
  ```bash
  python scripts/avaliar_rastreabilidade.py
  ```

> ⚠️ As métricas atuais comprovam que a instrumentação funciona ponta a ponta (retrieval → prompt → citação → log → métrica), **não** que as respostas são corretas. A "precisão de citação" só verifica se o id citado existe nas fontes, não se a fonte sustenta semanticamente a afirmação — refinamento previsto como próximo passo.

---

## 🧭 Fluxo e Arquitetura  

1. **Extração:** dados públicos são obtidos da API de Dados Abertos do Senado.  
2. **Tratamento:** limpeza, normalização e estruturação dos dados (módulo `data/`), com id estável por registro.  
3. **Análise com IA:** retrieval das fontes relevantes + geração com LLM local, citando os registros usados (módulo `ai/local_llm_handler.py`).  
4. **Visualização e auditoria:** interface, dashboards e painel de rastreabilidade em `app/`.

---

## 🔒 Nota de segurança

- Não comite chaves de API em arquivos do repo.
- Use `.env` (já listado no `.gitignore`) para segredos.

---

## 👩‍💻 Autora  

**Ana Beatriz Carvalho Oliveira**  
📧 [beatriz.carvalho0804@gmail.com](mailto:beatriz.carvalho0804@gmail.com)  
🌐 [github.com/AnaBeatriz-Carvalho](https://github.com/AnaBeatriz-Carvalho)

