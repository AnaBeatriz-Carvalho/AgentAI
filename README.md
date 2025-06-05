# 🧠 Análise de Discursos do Senado com Agente Gemini + Classificação Temática

Este projeto utiliza inteligência artificial (IA) da Google (Gemini) para extrair, analisar, **classificar tematicamente** e interpretar discursos do Senado Federal brasileiro. Através de uma interface interativa feita com Streamlit, o usuário pode visualizar dados, gráficos e interagir com um agente IA para obter respostas baseadas nos discursos.

## 🚀 Funcionalidades

* 📆 **Seleção de período**: escolha um intervalo de até 30 dias para análise.
* 🗣️ **Extração automática de discursos** via API de Dados Abertos do Senado.
* 🧠 **Classificação temática automática** (Educação, Saúde, Economia, Segurança, Cultura, Meio Ambiente, etc.).
* 📈 **Gráfico interativo** com distribuição temporal dos discursos e média móvel.
* 🤖 **Consulta à IA Gemini**: perguntas personalizadas com base nos discursos.
* 💬 **Interface intuitiva e moderna** feita com Streamlit.

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
├── app_streamlit.py                   # Interface principal com Streamlit
├── agente_gemini.py                   # Configuração do modelo Gemini
├── classificacao_tematica.py          # Novo módulo de classificação automática por tema
├── extrair_discursos.py               # Extração dos discursos via API do Senado
├── grafico_levantamento.py            # Geração de gráficos interativos com Plotly
├── modelos_gemini_disponiveis.txt     # Lista de modelos Gemini compatíveis
├── .env                               # API Key da Gemini
├── requirements.txt                   # Dependências do projeto

```

---

🤖 Classificação Temática
Os discursos extraídos são automaticamente classificados em temas com auxílio do Gemini, como:

Educação

Saúde

Economia

Segurança

Meio Ambiente

Cultura

Direitos Humanos

Infraestrutura

Política

Outros

A classificação é exibida na interface para facilitar a análise contextual.

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


