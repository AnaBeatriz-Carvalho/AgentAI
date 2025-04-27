# 🏛️ Coleta e Classificação de Discursos do Senado Federal utilizando Agent AI

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://agentaiproject.streamlit.app/)

Este projeto tem como objetivo coletar discursos do Senado Federal utilizando a API de dados abertos e classificar automaticamente os temas de cada discurso com base no conteúdo dos seus resumos, aplicando técnicas de Inteligência Artificial.

## 📁 Estrutura do Projeto

O projeto é composto por três arquivos principais:

- **`legislativo_copilot.py`**  
  Script desenvolvido com o auxílio do GitHub Copilot. Realiza a coleta dos discursos e classifica os temas dentro da função, carregando o modelo a cada chamada (menos otimizado).

- **`legislativo_gpt.py`**  
  Versão otimizada com base nas orientações do ChatGPT: o modelo de classificação é carregado apenas uma vez, melhorando bastante o desempenho na classificação de múltiplos discursos.

- **`app_streamlit.py`**  
  Interface interativa criada com Streamlit, permitindo coletar discursos, visualizar gráficos e exportar relatórios em CSV e PDF.

## ⚙️ Tecnologias Utilizadas

- **Python 3.10+**
- [Streamlit](https://streamlit.io/)
- [Transformers (HuggingFace)](https://huggingface.co/transformers/)
- [ReportLab](https://www.reportlab.com/)
- [Plotly](https://plotly.com/python/)
- Pandas
- Requests
- Torch
- XML Parsing (`xml.etree.ElementTree`)

## 🚀 Como Executar Localmente

1. Clone o repositório:

   ```bash
   git clone https://github.com/AnaBeatriz-Carvalho/AgentAI.git
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Execute o aplicativo:

   ```bash
   streamlit run app_streamlit.py
   ```

4. Ou acesse diretamente:  
   👉 [https://agentaiproject.streamlit.app/](https://agentaiproject.streamlit.app/)

## 📊 Comparativo entre Versões de Scripts

| Script                   | Tempo de Execução* | Carregamento de Modelo |
|---------------------------|--------------------|-------------------------|
| `legislativo_copilot.py`   | ~509 segundos       | A cada chamada          |
| `legislativo_gpt.py`       | ~351 segundos       | Uma única vez           |

> *Tempo aproximado. Pode variar conforme a conexão e a máquina utilizada.

## 📌 Conclusão

O projeto demonstra como o uso de Inteligência Artificial pode modernizar e automatizar o levantamento de dados legislativos. A comparação entre versões evidencia a importância de boas práticas de desenvolvimento para otimizar o desempenho de aplicações de IA.

Enquanto o GitHub Copilot sugeriu uma abordagem funcional viável, foi a análise crítica apoiada no ChatGPT que levou a um ganho real de eficiência.

---

## 👨‍💻 Desenvolvedores

- Ana Beatriz Carvalho Oliveira  
- Alberto Bastos  
- Victor Caetano  

---


