# Handoff — Rastreabilidade no AgentAI

> Cole este conteúdo num novo chat CLI do projeto para retomar o trabalho com contexto completo.

## Contexto do projeto
AgentAI: app web (Python + Streamlit) que coleta dados abertos da API do Senado Federal,
classifica discursos por tema e responde perguntas em linguagem natural com **Mistral 7B Instruct**
local (servidor OpenAI-compatível em `http://localhost:1234/v1`, ex.: LM Studio), sob RAG simplificado
(busca estruturada na base local em DataFrame Pandas — não vetorial — seguida de geração).

Estrutura relevante:
- ETL: `src/data/data_processing.py`, `src/data/votacoes_handler.py`
- LLM: `src/ai/local_llm_handler.py`
- UI: `src/app/app_streamlit.py`
- Config: `src/config/constants.py`, `src/config/settings.py`
- Base: DataFrame Pandas em memória (+ cache `outputs/materias_cache.json`). **Não há SQLite.**

## Branch
Todo o trabalho foi feito na branch **`developer-v2`** (preferência da usuária; `main` fica estável).
As alterações **ainda NÃO foram commitadas** — estão no working tree de `developer-v2`.

## Tarefa original: auditoria de rastreabilidade
Verificar, com base no código real, dois sentidos:
- **(A)** Rastreabilidade no artefato: a resposta expõe quais registros a fundamentaram.
- **(B)** Estrutura para avaliar rastreabilidade: log/campo/script para medir, depois, a proporção
  de respostas com vínculo resposta→fonte.

### Veredito da auditoria (estado ANTES das mudanças)
- **(A) PARCIAL**: o DataFrame inteiro era despejado no prompt (`df.to_markdown`), mas a resposta não
  citava fontes, não havia IDs de discurso, e o prompt não pedia citação. A tabela aparecia na página,
  mas desligada da resposta específica.
- **(B) NÃO**: logs só guardavam pergunta/resposta truncadas (`[:50]`), sem as fontes; nenhum script
  de avaliação; nenhum schema com campo de fontes.

## O que foi IMPLEMENTADO (nesta sessão, em developer-v2)

**(A) — citar e expor fontes**
1. `src/config/constants.py`: nova constante `COL_ID_DISCURSO = "id_discurso"`.
2. `src/data/data_processing.py` (loop de extração ~linhas 80-99): cada discurso recebe `id_discurso`
   estável — usa `CodigoPronunciamento`/`Codigo` da API se existir; senão sequencial `D1, D2, …`.
3. `src/ai/local_llm_handler.py`:
   - `_selecionar_fontes(df, pergunta, limite=40)`: retrieval por palavra-chave (filtra Resumo/
     Parlamentar/Tema/Partido pelos termos da pergunta; fallback = amostra geral). O contexto do prompt
     passou a ser **esse subconjunto** (antes era o DF inteiro).
   - `prompt_qa`: agora instrui o modelo a fundamentar nas fontes e **citar por `[id_discurso]`**,
     proibindo ids fora da lista.
   - Na UI do chat: `st.expander("📚 Fontes utilizadas")` com a tabela dos discursos usados.

**(B) — log + métrica**
4. `_registrar_trace(pergunta, fontes, resposta)` em `local_llm_handler.py`: grava 1 linha JSON por
   consulta em `logs/qa_trace.jsonl` (`timestamp`, `pergunta`, `fontes_ids`, `n_fontes`, `resposta`).
5. `scripts/avaliar_rastreabilidade.py`: lê o JSONL e calcula **cobertura de recuperação**,
   **cobertura de citação** e **precisão de citação** (regex `[\[]([A-Za-z]?\d+)[\]]`).

## Verificação feita
- Lógica de `_selecionar_fontes` (match por tema + fallback) e `_registrar_trace`: validadas isoladas ✓
- `scripts/avaliar_rastreabilidade.py`: testado com trace sintético (66,7% / 33,3% / 66,7%) ✓
- `py_compile` em todos os arquivos alterados: OK ✓
- Asserção de colunas do teste existente (`tests/test_data_processing.py:45`) continua válida (issubset).

## ⚠️ Ambiente (importante)
- O `.venv` versionado é do **Windows** (`Scripts/python.exe`) — não roda no macOS.
- O Python do anaconda tem `streamlit` antigo (sem `cache_data`) e **sem `openai`** → o `pytest`
  completo NÃO roda nesse ambiente (falha pré-existente em `votacoes_handler.py:103`, não relacionada
  às mudanças).
- Foi criado um venv macOS **`.venv_mac/`** (já adicionado ao `.gitignore`) com `requirements.txt`
  instalado (streamlit 1.58.0). Use-o para rodar/testar:
  ```bash
  .venv_mac/bin/python -m streamlit run src/app/app_streamlit.py   # rodar app
  .venv_mac/bin/python -m pytest -q                                 # rodar testes
  .venv_mac/bin/python scripts/avaliar_rastreabilidade.py           # métrica de rastreabilidade
  ```
- Para o chat funcionar de verdade: LM Studio servindo o Mistral em `localhost:1234/v1` + internet
  (API do Senado).

## Pendências / próximos passos sugeridos
1. **Rodar `pytest` no `.venv_mac`** e corrigir o que aparecer (não rodado ainda nesta sessão por
   limitação de ambiente).
2. **Adicionar testes unitários** para `id_discurso` (em `test_data_processing.py`) e para
   `_selecionar_fontes` / `_registrar_trace`.
3. **Aplicar rastreabilidade também ao chat de VOTAÇÕES** (`app_streamlit.py:255-270`): hoje injeta só
   estatísticas agregadas e não passa `codigo_materia` ao prompt — mais fraco que o de discursos.
4. **Commit** das mudanças em `developer-v2` (não feito; aguardando decisão da usuária).
5. (Opcional) Trocar o retrieval por palavra-chave por algo mais robusto (sinônimos/embeddings) se
   precisar de recall melhor.

## Arquivos alterados/criados nesta sessão
- M `src/config/constants.py`
- M `src/data/data_processing.py`
- M `src/ai/local_llm_handler.py`
- A `scripts/avaliar_rastreabilidade.py`
- A `HANDOFF_RASTREABILIDADE.md` (este arquivo)
- M `.gitignore` (ignora `.venv_mac/`)
- (runtime) `logs/qa_trace.jsonl` é gerado ao usar o chat
