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

---

# ATUALIZAÇÃO — Sessão 2 (Windows, 2026-06-06)

> Continuação direta do trabalho acima. Tudo segue em **`developer-v2`** e **ainda não commitado**.
> Ambiente agora é **Windows** (não macOS): o `.venv` versionado (`.venv\Scripts\python.exe`, Python
> 3.11.9) estava **vazio**; rodamos `pip install -r requirements.txt`. O LM Studio **está funcionando**
> nesta máquina (Mistral em `localhost:1234/v1`), então o chat foi testado de verdade.

## O que foi feito nesta sessão (em ordem)

### 1. Painel de rastreabilidade na interface (sem terminal)
- **Novo módulo `src/utils/rastreabilidade.py`** com o núcleo das métricas (DRY): `TRACE_PADRAO`,
  `carregar_registros` (lê com `utf-8-sig`), `avaliar` e **`avaliar_por_origem`** (segmenta por
  discurso/votação).
- `scripts/avaliar_rastreabilidade.py` virou **wrapper fino** que importa esse módulo (CLI inalterado).
- **Nova aba "📊 Rastreabilidade"** em `src/app/app_streamlit.py`: mostra as 3 porcentagens (gerais e por
  origem) com `st.metric`, botão "🔄 Atualizar", expander explicativo e estado vazio com instruções.

### 2. Rastreabilidade no chat de VOTAÇÕES (pendência #3 da Sessão 1 — feita)
- Nova função `responder_pergunta_votacao_local(...)` em `local_llm_handler.py`: id citável `V1..Vn` por
  voto, retrieval nos votos, citação `[V…]`, expander de fontes e trace `origem="votacao"`. Plugada em
  `app_streamlit.py` no lugar do bloco inline.
- **Bug latente corrigido de brinde**: o bloco antigo de votações usava `client`/`_CFG` que **nunca eram
  importados** em `app_streamlit.py` → qualquer pergunta de votação lançava `NameError`. Agora roteia pela
  função do handler.

### 3. Fix do `tabulate` (ImportError ao perguntar)
- `df.to_markdown()` exige `tabulate`, que estava **comentado** no `requirements.txt`. Descomentado +
  instalado (`tabulate 0.10.0`). Bug pré-existente, exposto pelo venv recém-criado.

### 4. Fix de estouro de contexto (HTTP 400 `n_keep > n_ctx`)
- O modelo no LM Studio está com janela `n_ctx = 4096`; o prompt de discursos chegava a ~4819 tokens
  (até 40 fontes em 16.000 chars) → 400. **Guardrail** em `src/config/constants.py`:
  `MAX_FONTES_PROMPT = 15` e `MAX_CHARS_CONTEXTO_PROMPT = 7000`, usados nos dois chats. Para respostas
  mais ricas: aumentar `n_ctx` no LM Studio e, se quiser, subir essas constantes.

### 5. Fix da citação 0% + qualidade das respostas (o ponto-chave)
- **Causa do 0%**: o `id_discurso` é o código real do Senado (`522046`…). O modelo citava `[D3]`
  (inventado, copiando o exemplo), `[D522035]` (código com "D") ou agrupado `[D522046, D522043, …]` —
  nada casava com `fontes_ids` nem com o regex. (Votações já funcionava por usar `V1..Vn`.)
- **Correção**: discursos agora ganham um **ref curto citável `D1..Dn`** por consulta (espelha votações),
  que casa com o exemplo `[D3]` e o regex. O código real do Senado continua visível na tabela de fontes
  (`id_discurso`) e é gravado no trace no novo campo **`fontes_codigos`** (auditoria); `fontes_ids` passa
  a guardar os refs.
- **Prompt anti-alucinação**: separa "estatísticas agregadas (toda a amostra)" de "fontes recuperadas
  (cite só estas)"; declara que **os autores são senadores** (corrige a confusão senador/deputado);
  exige **um id por colchete** (`[D1] [D3]`, nunca `[D1, D3]`); proíbe detalhes fora das fontes.
- `_registrar_trace` ganhou parâmetro opcional `fontes_codigos`.

### 6. Robustez do eval script
- `≥` trocado por `>=` nos `print` (evita `UnicodeEncodeError` no console cp1252 do Windows); leitura
  passou a `utf-8-sig` (ignora BOM).

## Resultados medidos (chat real, LM Studio ligado)

Antes do fix de citação (3 perguntas): recuperação **100%**, citação **0%**, precisão **0%**.
Depois do fix (4 perguntas novas, log zerado): recuperação **100%**, citação **50%**, precisão
**100% (5/5)**. → O encanamento (retrieval → prompt → citação → log → métrica) funciona ponta a ponta.

## ⚠️ Avaliação crítica das porcentagens (importante para discutir)

As porcentagens hoje **provam que a instrumentação funciona, não que as respostas são boas/corretas**:
1. **Amostra minúscula** (4 perguntas) — estatisticamente sem significado ainda.
2. **"Cobertura de recuperação" é ~sempre 100% por construção** — `_selecionar_fontes` tem fallback que
   sempre devolve algo; só cai com DataFrame vazio. Métrica quase decorativa.
3. **"Precisão de citação" só checa se o id existe nas fontes, não se a fonte sustenta a frase** — dá pra
   ter 100% citando fontes que não embasam nada. Noção rasa de rastreabilidade.
4. **"Cobertura de citação" é confundida pelo tipo de pergunta** — perguntas agregadas ("quantos
   senadores?", "quais partidos?") legitimamente não citam fonte específica e derrubam a métrica mesmo
   com resposta correta.

## Pendências / próximos passos (atualizado)

1. **Guardrail de citação agrupada** (proposto, ainda não feito): normalizar a resposta antes de
   exibir/logar — `[D1, D4, D9]` → `[D1] [D4] [D9]`. Recupera citações hoje perdidas (ex.: Q2 da última
   rodada) sem depender do modelo obedecer. Mantém precisão honesta (id inexistente continua inválido).
2. **Métrica mais significativa**: segmentar por tipo de pergunta (factual vs agregada) e medir citação só
   onde faz sentido; checar **suporte semântico** (termo/tema citado aparece no Resumo do discurso, ou
   LLM-juiz); contabilizar **alucinação de id** (ids citados que não existem em fonte nenhuma).
3. **Classificação de tema** é por palavra-chave (`classificar_tema_local`) e **super-atribui "Política"**
   (14 de 41). Melhorar exigiria LLM/embeddings.
4. **Commit** em `developer-v2` (ainda não feito; aguardando decisão).
5. (Opcional) Aumentar `n_ctx` no LM Studio + subir `MAX_FONTES_PROMPT`/`MAX_CHARS_CONTEXTO_PROMPT` para
   respostas mais ricas.

## Estado de testes
- `pytest -q` → **43 passed** (testes novos: `id_discurso` sequencial/por código; `_selecionar_fontes`
  match/acento/ranking/fallback/colunas custom; `_registrar_trace` incl. `fontes_codigos`; módulo
  `rastreabilidade` `avaliar`/`avaliar_por_origem`/BOM).

## Como rodar nesta máquina (Windows)
```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app/app_streamlit.py   # app (porta 8501)
.\.venv\Scripts\python.exe -m pytest -q                                # testes
.\.venv\Scripts\python.exe scripts\avaliar_rastreabilidade.py          # métrica (terminal)
```

## Arquivos alterados/criados na Sessão 2
- M `src/ai/local_llm_handler.py` (votações QA, guardrail de contexto, refs `D1..Dn`, prompt, trace)
- M `src/config/constants.py` (`MAX_FONTES_PROMPT`, `MAX_CHARS_CONTEXTO_PROMPT`)
- M `src/app/app_streamlit.py` (aba 📊 Rastreabilidade + wire-in das votações)
- A `src/utils/rastreabilidade.py` (núcleo das métricas)
- M `scripts/avaliar_rastreabilidade.py` (wrapper fino + `>=`/`utf-8-sig`)
- M `requirements.txt` (`tabulate` descomentado)
- A `tests/test_avaliar_rastreabilidade.py` (reescrito para o módulo) e M `tests/test_data_processing.py`,
  M `tests/test_local_llm_handler.py`
- (runtime) `logs/qa_trace.jsonl` foi **zerado** para refletir só o comportamento corrigido
