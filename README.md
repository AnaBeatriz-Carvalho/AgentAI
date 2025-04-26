
# 🏛️ Coleta e Classificação de Discursos do Senado Federal utilizando Agent AI

Este projeto tem como objetivo coletar discursos do Senado Federal utilizando a API de dados abertos e classificar automaticamente os temas de cada discurso com base no conteúdo de seus resumos.

## 📁 Estrutura do Projeto

O projeto é composto por dois scripts Python independentes:

- **`legislativo_copilot.py`**  
  Desenvolvido com o auxílio do GitHub Copilot, este script realiza a coleta dos discursos e classifica os temas diretamente dentro da função, usando a biblioteca `transformers` com o modelo `facebook/bart-large-mnli`. O modelo é carregado a cada chamada de classificação.

- **`legislativo_gpt.py`**  
  Versão otimizada com base nas sugestões do ChatGPT. Aqui, o modelo de classificação é carregado uma única vez fora da função, o que melhora significativamente o desempenho ao classificar múltiplos discursos.

## ⚙️ Tecnologias Utilizadas

- Python 3.10+
- `requests`
- `xml.etree.ElementTree`
- `transformers` 
- Modelo: `facebook/bart-large-mnli`

## 🚀 Como Executar

1. Instale as dependências:
   ```bash
   pip install transformers requests
   ```

2. Execute um dos scripts diretamente:
   ```bash
   python legislativo_copilot.py
   ```
   ou
   ```bash
   python legislativo_gpt.py
   ```

3. O terminal exibirá os discursos obtidos e seus respectivos temas.

## 📊 Comparativo entre versões

| Versão               | Tempo de execução* | Carregamento do modelo |
|----------------------|--------------------|-------------------------|
| `legislativo_copilot.py` | ~509 segundos       | A cada chamada          |
| `legislativo_gpt.py`     | ~351 segundos       | Uma vez só              |

> *Tempo estimado com base em execução local. Pode variar dependendo da conexão e da máquina.

## 📌 Conclusão

O projeto demonstra como ferramentas de inteligência artificial podem auxiliar na automação de tarefas legislativas. A diferença entre as versões evidencia o impacto de boas práticas de programação: o uso eficiente de recursos, como o carregamento único de modelos pesados, pode reduzir significativamente o tempo de execução. Enquanto o GitHub Copilot sugeriu uma abordagem funcional viável, foi a análise crítica com apoio do ChatGPT que levou à otimização do desempenho.

## Desenvolvedores
Ana Beatriz Carvalho Oliveira,
Alberto Bastos,
Victor Caetano
