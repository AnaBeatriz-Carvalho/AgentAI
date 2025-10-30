# 🏛️ Análise de Discursos do Senado com Agente Gemini

Este projeto apresenta uma aplicação web interativa para a análise automatizada de discursos e pronunciamentos do Senado Federal brasileiro, utilizando a API de Dados Abertos do Senado e o poder da Inteligência Artificial Generativa.

A aplicação permite que pesquisadores, jornalistas e cidadãos explorem o conteúdo parlamentar de forma intuitiva, realizando buscas por período, visualizando tendências temáticas e "conversando" com os dados através de um agente de linguagem natural.

---

## 🚀 Funcionalidades Principais

* **Sessão de Votações:** Acompanhe as votações do plenário, com detalhes sobre o que foi votado, o resultado e a posição de cada parlamentar.
* **Análise de Discursos:** Explore discursos e pronunciamentos, realize buscas por período e visualize as tendências dos temas debatidos.
* **Classificação com IA:** Utiliza a API do Gemini para analisar e classificar o conteúdo de discursos e matérias em categorias temáticas (Saúde, Educação, Economia, etc.).
* **Agente Conversacional (Chatbot):** Permite que o usuário "converse com os dados", fazendo perguntas em linguagem natural sobre as informações carregadas (votações, discursos, etc.) para receber respostas elaboradas.
* **Dashboard Interativo:** Apresenta visualizações de dados, como a distribuição de temas e o volume de atividades ao longo do tempo, utilizando gráficos gerados com Plotly.
* **Interface Amigável:** Desenvolvida com Streamlit para proporcionar uma experiência de usuário limpa, simples e responsiva.

---

## ⚙️ Tecnologias Utilizadas

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
    # opção A: usando o helper (recomendado)
    python run_app.py

    # opção B: invocando diretamente o Streamlit
    streamlit run src/app/app_streamlit.py
    ```

6.  Abra seu navegador e acesse o endereço `http://localhost:8501`.

---

## 📂 Estrutura do Projeto

```
AgentAI/
│
├── src/                    # Código-fonte reorganizado em pacote
│   ├── app/
│   │   └── app_streamlit.py     # UI (Streamlit)
│   ├── data/
│   │   ├── data_processing.py   # Extração e transformação de discursos
│   │   └── votacoes_handler.py   # Extração e transformação de votações
│   ├── ai/
│   │   └── gemini_handler.py    # Lógica de interação com Gemini
│   ├── utils/
│   │   └── helpers.py           # Utilitários pequenos
│   └── config/
│       └── settings.py          # Carregamento de variáveis de ambiente
├── run_app.py              # Script auxiliar para iniciar a aplicação
├── requirements.txt
├── .env                    # Arquivo local para variáveis de ambiente (não incluído no repo)
```

---


## ✍️ Autora

* **Ana Beatriz Carvalho Oliveira** - [beatriz.carvalho0804@gmail.com](beatriz.carvalho0804@gmail.com)

---

## 🤝 Contribuição

Contribuições são muito bem-vindas! Se você tem ideias para novas funcionalidades, melhorias no código ou correções de bugs, sinta-se à vontade para abrir uma *issue* ou enviar um *pull request*.
