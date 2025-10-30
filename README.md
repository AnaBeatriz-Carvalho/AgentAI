# 🏛️ Análise de Discursos do Senado com Agente Gemini  

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Streamlit](https://img.shields.io/badge/Framework-Streamlit-red)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)

Aplicação web interativa para **análise automatizada de discursos, votações e pronunciamentos** do Senado Federal brasileiro.  
Desenvolvida com **Streamlit** e **IA Generativa (Google Gemini)**, a ferramenta permite explorar dados públicos de forma intuitiva, combinando transparência, ciência de dados e aprendizado de máquina.

---

## 🚀 Funcionalidades Principais  

- **🗳️ Sessão de Votações:** Acompanhe votações plenárias com detalhes sobre matérias, resultados e posições parlamentares.  
- **🗣️ Análise de Discursos:** Busque discursos por período, tema ou parlamentar e visualize tendências de debate.  
- **🧠 Classificação com IA:** Utilize o modelo **Gemini** para categorizar discursos em temas como *Educação, Economia, Saúde*, entre outros.  
- **💬 Agente Conversacional:** Faça perguntas em linguagem natural sobre votações e discursos e obtenha respostas explicativas.  
- **📊 Dashboard Interativo:** Visualize métricas e séries temporais com **Plotly**.  
- **🪶 Interface Moderna:** Desenvolvida com **Streamlit**, intuitiva e responsiva.

---

## ⚙️ Tecnologias Utilizadas  

| Categoria | Ferramenta |
|------------|------------|
| **Linguagem** | Python 3.10+ |
| **Framework Web** | Streamlit |
| **Manipulação de Dados** | Pandas |
| **IA Generativa** | Google Gemini (`google-generativeai`) |
| **Visualização** | Plotly |
| **HTTP Requests** | Requests |
| **Testes Automatizados** | Pytest |
| **Ambiente** | Python-dotenv |

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
│   │   └── gemini_handler.py     # Integração com a API do Gemini
│   ├── utils/
│   │   └── helpers.py            # Funções auxiliares gerais
│   └── config/
│       └── settings.py           # Carregamento de variáveis de ambiente
│
├── tests/                        # Testes automatizados com pytest
│   ├── test_data_processing.py
│   ├── test_votacoes_handler.py
│   ├── test_gemini_handler.py
│   └── conftest.py
│
├── run_app.py                    # Script auxiliar para iniciar a aplicação
├── requirements.txt              # Dependências do projeto
├── .env.example                  # Exemplo de variáveis de ambiente
├── .env                          # Arquivo real de ambiente 
└── README.md
```

---

## 💻 Instalação e Execução  

### Pré-requisitos  
- Python 3.10+  
- Chave de API válida do [Google AI Studio](https://aistudio.google.com/app/apikey)

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

4. **Configure as variáveis de ambiente:**
   O projeto fornece um arquivo modelo `.env.example` com os nomes das variáveis esperadas.

   - Copie o arquivo:
     ```bash
     cp .env.example .env
     ```
     *(no Windows: `copy .env.example .env`)*

   - Abra o novo arquivo `.env` e adicione sua chave da API:
     ```
     GOOGLE_API_KEY="SUA_CHAVE_DE_API_AQUI"
     ```

5. **Execute a aplicação:**
   ```bash
   python run_app.py
   ```
   ou  
   ```bash
   streamlit run src/app/app_streamlit.py
   ```

6. **Acesse no navegador:**  
   [http://localhost:8501](http://localhost:8501)

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
3. **Análise com IA:** classificação temática via `Gemini` (módulo `ai/`).  
4. **Visualização:** interface e dashboards em `app/`.

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

