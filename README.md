# 🏛️ Análise de Atividades do Senado (LLM Local + Streamlit)

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)

Aplicação web interativa para analisar **pronunciamentos (discursos)** e **votações** do Senado Federal (dados públicos), com:

- **LLM local** para classificação/análise de discursos e chat com os dados (via API OpenAI-compatível, ex.: LM Studio)

---

## 🚀 Funcionalidades

- **🗣️ Discursos:** coleta por período, classificação temática, resumo e atributos (agenda, tom, posicionamento etc.)
- **📊 Dashboard:** gráficos (Plotly) e tabela filtrável
- **💬 Chat com os dados:** perguntas em linguagem natural usando o contexto da amostra coletada
- **🗳️ Votações:** exploração por período, filtros por partido/parlamentar e export CSV

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
│   │   └── app_streamlit.py      # Interface principal (Streamlit)
│   ├── data/
│   │   ├── data_processing.py    # Processamento e limpeza dos discursos
│   │   └── votacoes_handler.py   # Extração e organização das votações
│   ├── ai/
│   │   ├── local_llm_handler.py  # LLM local (OpenAI-compatível / LM Studio)
│   ├── utils/
│   │   └── helpers.py            # Funções auxiliares gerais
│   └── config/
│       └── settings.py           # Carregamento de variáveis de ambiente
│
├── tests/                        # Testes automatizados com pytest
│   ├── test_data_processing.py
│   ├── test_votacoes_handler.py
│   └── conftest.py
│
├── run_app.py                    # Script auxiliar para iniciar a aplicação
├── requirements.txt              # Dependências do projeto
├── .env.example                  # Exemplo de variáveis de ambiente (NÃO comite chaves reais)
├── .env                          # Variáveis locais (NÃO comite)
└── README.md
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
       LOCAL_LLM_MODEL="qwen3-vl-4b"
       ```

5. **Inicie o LLM local (LM Studio):**

   - Abra o LM Studio
   - Carregue um modelo e inicie o **Local Server** no endpoint `http://localhost:1234/v1`
   - O projeto está configurado para usar um modelo chamado `qwen3-vl-4b` (ajuste via `.env` se necessário)

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
pytest -q
```

---

## 🧭 Fluxo e Arquitetura  

1. **Extração:** dados públicos são obtidos da API de Dados Abertos do Senado.  
2. **Tratamento:** limpeza, normalização e estruturação dos dados (módulo `data/`).  
3. **Análise com IA:** classificação/análise com LLM local (módulo `ai/local_llm_handler.py`).  
4. **Visualização:** interface e dashboards em `app/`.

---

## 🔒 Nota de segurança

- Não comite chaves de API em arquivos do repo.
- Use `.env` (já listado no `.gitignore`) para segredos.

---


## 🤝 Contribuindo  

Contribuições são bem-vindas!  
Siga o fluxo padrão de contribuição:

```bash
git checkout -b feature/nova-funcionalidade
git commit -m "feat: adiciona nova funcionalidade"
git push origin feature/nova-funcionalidade
```

Abra um **Pull Request** e descreva suas alterações.  
Sugestões de melhorias, correções e documentação são sempre valorizadas 💡  

---

## 👩‍💻 Autora  

**Ana Beatriz Carvalho Oliveira**  
📧 [beatriz.carvalho0804@gmail.com](mailto:beatriz.carvalho0804@gmail.com)  
🌐 [github.com/AnaBeatriz-Carvalho](https://github.com/AnaBeatriz-Carvalho)

