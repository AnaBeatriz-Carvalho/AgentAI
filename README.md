# 🧠 Análise de Discursos do Senado com Agente Gemini

Este projeto utiliza inteligência artificial (IA) da Google (Gemini) para extrair, analisar e interpretar discursos do Senado Federal brasileiro. Através de uma interface interativa feita com Streamlit, é possível visualizar dados, gráficos e interagir com um agente IA para obter respostas baseadas nos discursos.

## 🚀 Funcionalidades

* 🗖️ **Seleção de período**: escolha um intervalo de até 30 dias para análise.
* 🗣️ **Extração automática de discursos** via API de Dados Abertos do Senado.
* 📈 **Visualização interativa** com gráfico de discursos por data e média móvel.
* 🤖 **Consulta a IA Gemini**: faça perguntas e receba respostas contextualizadas com base nos discursos extraídos.
* 💬 **Interface simples e intuitiva** feita com Streamlit.


## ⚒️ Como Executar Localmente

### 1. Clone o repositório

```bash
git clone https://github.com/AnaBeatriz-Carvalho/AgentAI.git
```

### 2. Crie um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure a chave da API Gemini

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
GEMINI_API_KEY=sua_chave_de_api
```

> Você pode obter uma chave gratuita ou paga em [Google AI Studio](https://makersuite.google.com/app/apikey).

---

## ▶️ Executar a Aplicação

```bash
streamlit run app_streamlit.py
```

---

## 📂 Estrutura do Projeto

```
├── app_streamlit.py                  # Interface principal com Streamlit
├── agente_gemini.py                 # Configuração da API do Gemini
├── extrair_discursos.py            # Módulo de extração de dados do Senado
├── grafico_levantamento.py        # Geração de gráfico interativo com Plotly
├── modelos_gemini_disponiveis.txt # Lista de modelos Gemini suportados
├── .env                            # Armazena a API key
└── requirements.txt                # Lista de dependências do projeto
```

---

## 🤖 Modelos Gemini Suportados

O projeto é compatível com diversos modelos do Gemini. O padrão atual é `gemini-1.5-flash`, mas você pode trocar no código ou expandir a interface para selecionar outros modelos.

Veja a lista completa em [`modelos_gemini_disponiveis.txt`](modelos_gemini_disponiveis.txt).

---

## 📌 Observações

* Limite de 30 dias por consulta devido à API do Senado.
* A IA utiliza apenas parte dos discursos para economizar tokens.
* Em caso de erro "quota exceeded", verifique o plano de sua API.

---


## 👨‍💻 Desenvolvedores

- Ana Beatriz Carvalho Oliveira  
- Alberto Bastos  
- Victor Caetano  


