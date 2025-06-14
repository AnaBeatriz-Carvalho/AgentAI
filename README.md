# 🏛️ Análise de Discursos do Senado com Agente Gemini

Este projeto apresenta uma aplicação web interativa para a análise automatizada de discursos e pronunciamentos do Senado Federal brasileiro, utilizando a API de Dados Abertos do Senado e o poder da Inteligência Artificial Generativa do Google Gemini.

A aplicação permite que pesquisadores, jornalistas e cidadãos explorem o conteúdo parlamentar de forma intuitiva, realizando buscas por período, visualizando tendências temáticas e "conversando" com os dados através de um agente de linguagem natural.

Este trabalho foi desenvolvido no âmbito do Programa de Pós-Graduação em Ciência da Computação (PROCC) da Universidade Federal de Sergipe.

---

## 🌟 Funcionalidades Principais

* **Extração de Dados em Tempo Real:** Conecta-se diretamente à API de Dados Abertos do Senado para buscar pronunciamentos parlamentares por períodos de data selecionados.
* **Classificação Temática com IA:** Utiliza a API do Google Gemini para analisar o resumo de cada discurso e classificá-lo em tempo real em categorias como "Saúde", "Educação", "Economia", etc.
* **Dashboard Interativo:** Apresenta visualizações de dados, como a distribuição de temas e o volume de discursos ao longo do tempo, utilizando gráficos gerados com Plotly.
* **Agente Conversacional (Chatbot):** Permite que o usuário faça perguntas em linguagem natural sobre os dados carregados. O Agente Gemini analisa o contexto dos discursos e fornece respostas elaboradas.
* **Interface Amigável:** Desenvolvida com Streamlit para proporcionar uma experiência de usuário limpa, simples e responsiva.

---

## 🚀 Tecnologias Utilizadas

* **Linguagem:** Python 3.10+
* **Interface Web:** Streamlit
* **Manipulação de Dados:** Pandas
* **Inteligência Artificial Generativa:** Google Gemini API (via `google-generativeai`)
* **Visualização de Dados:** Plotly
* **Requisições HTTP:** Requests

---

## ⚙️ Instalação e Execução

Siga os passos abaixo para executar o projeto em seu ambiente local.

### Pré-requisitos
* Python 3.10 ou superior instalado.
* Uma chave de API do Google Gemini. Você pode obter uma no [Google AI Studio](https://aistudio.google.com/app/apikey).

### Passos

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/AnaBeatriz-Carvalho/AgentAI.git](https://github.com/AnaBeatriz-Carvalho/AgentAI.git)
    cd AgentAI
    ```

2.  **Crie e ative um ambiente virtual (recomendado):**
    ```bash
    # Para macOS/Linux
    python3 -m venv venv
    source venv/bin/activate

    # Para Windows
    python -m venv venv
    .\venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure sua chave de API:**
    * Crie um arquivo chamado `.env` na raiz do projeto.
    * Dentro deste arquivo, adicione sua chave da seguinte forma:
        ```
        GOOGLE_API_KEY="SUA_CHAVE_DE_API_AQUI"
        ```

5.  **Execute a aplicação Streamlit:**
    ```bash
    streamlit run app_streamlit.py
    ```

6.  Abra seu navegador e acesse o endereço `http://localhost:8501`.

---

## 📂 Estrutura do Projeto

```
AgentAI/
│
├── 📄 app_streamlit.py      # Script principal da aplicação, responsável pela interface do usuário (UI)
├── 📄 data_processing.py    # Módulo para extrair, processar e classificar os dados da API do Senado
├── 📄 gemini_handler.py     # Módulo que gerencia a lógica do chatbot e a interação com o Gemini
├── 📄 .env                  # Arquivo para armazenar a chave da API do Google (deve ser criado localmente)
├── 📄 requirements.txt      # Lista de dependências Python do projeto
└── 📄 README.md             # Este arquivo
```

---


## ✍️ Autores

* **Alberto Luciano de Souza Bastos** - [alberto.bastos@academico.ufs.br](mailto:alberto.bastos@academico.ufs.br)
* **Ana Beatriz Carvalho Oliveira** - [anabeatrizcarvalho@academico.ufs.br](mailto:anabeatrizcarvalho@academico.ufs.br)
* **Victor Caetano Menezes** - [victormenezes41@academico.ufs.br](mailto:victormenezes41@academico.ufs.br)

