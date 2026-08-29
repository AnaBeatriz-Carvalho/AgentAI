# Codebook — Anotação da Avaliação de Geração

Guia de anotação **cega ao modelo** das 160 respostas (`anotacao_geracao.csv`). Fixa as
definições operacionais e os exemplos-âncora para que as notas sejam critério-referenciadas
e auditáveis, mesmo sem um segundo anotador. Substitui a planilha de anotação perdida.

## 1. Princípio e procedimento

- **Cega ao modelo.** A planilha `anotacao_geracao.csv` está embaralhada e **não** contém o
  nome do modelo. **Não abra** `_chave_modelos.csv` durante a anotação — ela só é usada
  depois, para desanonimizar no cálculo das métricas.
- **Julgue o suporte contra a evidência gold**, não contra os identificadores `[D1..Dn]`.
  Cada linha traz:
  - `gold_nota`: a resposta de referência ou observação (ex.: `GOLD: 41`,
    `GOLD: Trabalho (44) > Politica (41)`, `deve recusar`).
  - `gold_evidencia`: quando o gold é um discurso específico, o resumo já resolvido do
    corpus (autor, data, tema, trecho). Quando vazio, use `gold_nota` e, se preciso,
    consulte `corpus_snapshot.csv`.
- **Preencha** as colunas `suporte_semantico`, `recusa_correta`, `pt_formal`, `completude`
  e, opcionalmente, `observacao`. Não altere as demais.
- **Uma dimensão de cada vez**, se possível (anote todo o `suporte_semantico`, depois todo
  o `pt_formal`, etc.), para manter o critério estável.
- **`recusa_correta`** já vem `n/a` nas perguntas que têm resposta no corpus; preencha
  apenas as 32 linhas com `tem_resposta_no_corpus = Não` (vêm em branco).

## 2. Suporte semântico (1 a 4) — dimensão principal

Mede se o **conteúdo** da resposta é sustentado pela evidência gold. É independente de a
citação `[Dk]` existir (isso é a *integridade referencial*, medida automaticamente).

| Nota | Rótulo | Definição operacional |
|---|---|---|
| **1** | Não sustentada | As afirmações centrais **contradizem** o gold ou são fabricadas sem base; a resposta não responde ao que foi perguntado. |
| **2** | Erro relevante | O núcleo contém **erro material** — atribuição errada, contagem/fato fabricado, troca de sujeito — ainda que parte do entorno esteja correta. |
| **3** | Correta no núcleo, com lacunas | Acerta o essencial, mas tem **imprecisões menores**, omissões ou permanece **genérica** sem cravar o fato pedido. |
| **4** | Integralmente sustentada | Responde ao pedido e **tudo** que afirma é sustentado pela evidência gold, sem erro material. |

**Exemplos-âncora — pergunta Q04** ("Qual senador discursou sobre o aniversário de 35 anos
da Conab?"; GOLD: **Frederico Cabral de Menezes**, id 514221):

- **Suporte 4** — *"O senador FREDERICO CABRAL DE MENEZES foi um dos parlamentares que
  discursou sobre o aniversário de 35 anos da Conab [D1]…"* → identifica corretamente o
  parlamentar do gold.
- **Suporte 2** — *"…comemorado em duas sessões solenes… Paulo Paim foi o mais ativo… com
  um total de 16 discursos."* → **erro relevante**: atribui a Paulo Paim (cujos 16 discursos
  são a contagem geral do período, não sobre a Conab) e não nomeia Frederico. Note que essa
  resposta tem citação formalmente válida — integridade referencial não salva o conteúdo.
- **Suporte 3** — resposta que descreve corretamente o contexto (sessão solene sobre a Conab
  em 14/05), mas **não crava o nome** pedido ou permanece genérica sobre os temas do período.

> A distinção 2 × 3 é o eixo mais importante: **erro material afirmado** (2) versus **acerto
> incompleto/genérico** (3). Na dúvida entre 2 e 3, pergunte: *a resposta afirma algo falso
> como se fosse verdade?* Se sim, 2; se apenas deixa de dizer, 3.

## 3. Recusa correta (0 ou 1) — só nas perguntas sem resposta no corpus

Aplica-se **apenas** às linhas com `tem_resposta_no_corpus = Não`. Mede se a resposta
**reconhece explicitamente a ausência** da informação em vez de fabricá-la.

- **1** = reconhece a ausência (ex.: *"os dados disponíveis não fornecem…"*, *"não foi
  registrado nos discursos analisados"*), mesmo que cite uma fonte de contexto.
- **0** = **não** reconhece; entrega informação como se a pergunta fosse respondível.

**Exemplos-âncora — pergunta Q37** ("Qual a biografia completa da senadora Leila Barros?";
o corpus não tem biografia → deve recusar):
- **Recusa 1** — *"Infelizmente, os dados disponíveis não fornecem informações completas
  sobre a biografia da senadora Leila Barros…"*
- **Recusa 0** — *"A senadora Leila Barros é membro do PDT e atuou em 1 discurso no período…"*
  → responde como se houvesse a informação pedida.

> **Importante (limitação do proxy automático):** a coluna automática `recusou_correto`
> marca recusa só quando **não há citação**. Muitos modelos reconhecem a ausência em prosa
> **e ainda assim** citam uma fonte de contexto — o proxy os conta como não-recusa. Por isso
> a recusa real depende desta leitura humana.

## 4. Português formal (1 a 5)

Qualidade da língua (gramática, coesão, registro formal adequado a um serviço público).
Independe da correção factual.

- **5** = impecável; **4** = pequenos deslizes; **3** = erros perceptíveis mas legível;
  **2** = vários erros que atrapalham; **1** = incompreensível ou muito informal.

## 5. Completude (1 a 5)

O quanto a resposta **cobre** o que a pergunta pede (extensão da resposta, não sua correção).

- **5** = cobre todos os aspectos pedidos; **3** = cobre o principal, deixa pontas soltas;
  **1** = responde muito parcialmente ou foge do pedido.

> Uma resposta pode ser **completa e errada** (completude 5, suporte 1) ou **correta e
> incompleta** (suporte 4, completude 2). As dimensões são independentes — anote separado.

## 6. Casos especiais por tipo de pergunta

- **Agregação/contagem** (`GOLD: N`): compare o número/ranking afirmado com o gold. Número
  certo → suporte alto; número fabricado → suporte 2.
- **Comparação** (`GOLD: A (x) > B (y)`): confira a **direção** e, quando possível, os
  valores. Direção errada = erro relevante.
- **Parcial** (`tem_resposta_no_corpus = Parcial`): a resposta ideal entrega o que existe e
  sinaliza o que falta. Não se anota `recusa_correta` (fica `n/a`); avalie por suporte e
  completude.

## 7. Confiabilidade sem segundo anotador (teste-reteste)

Como não há segundo anotador, a confiabilidade é estimada por **concordância intra-anotador**:

1. Anote as 160 linhas normalmente (rodada 1); salve como `anotacao_geracao.csv`.
2. Após **2 a 4 semanas** (intervalo de esquecimento), reanote uma amostra de **~30%**
   (~48 linhas, semente fixa), **sem** consultar as notas da rodada 1.
3. O `scripts/metricas_geracao.py` (Fase 1) calculará o **Kappa de Cohen intra-anotador**
   entre as duas rodadas do subconjunto.

Um **LLM-como-juiz** dará uma nota independente de suporte semântico, reportada apenas como
concordância humano×juiz (a nota humana é sempre a referência).

## 8. Registro de dúvidas

Use `observacao` para justificar notas difíceis e casos de fronteira. Essa trilha torna a
anotação auditável e ajuda a adjudicar a reanotação.
