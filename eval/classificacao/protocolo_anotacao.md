# Protocolo de anotação do gabarito ouro — Classificação temática

> Experimento da **cláusula (a)** da hipótese (PROCC/UFS, AgentAI): acurácia da
> classificação temática do Mistral 7B vs. baselines sem LLM, contra gabarito anotado
> por humano. Este protocolo é fixado **antes** da anotação (requisito metodológico).

## 1. Objeto e corpus

- **Corpus:** `eval/corpus_snapshot.csv` — 152 discursos do Senado (05–16/maio/2025),
  congelado. A unidade de anotação é o **Resumo** de cada discurso (campo `Resumo`),
  acompanhado de `Parlamentar`/`Partido`/`UF`/`Data` como contexto auxiliar.
- **Tarefa:** atribuir a cada discurso **exatamente um** rótulo da taxonomia consolidada
  (Seção 2). Classificação de rótulo único (single-label), multiclasse.

## 2. Taxonomia (fonte: `taxonomia.json`)

Cinco rótulos, ancorados no catálogo oficial de áreas temáticas do Senado e consolidados
para garantir estabilidade das métricas no corpus de 152 discursos:

| Rótulo | Abrange (resumo) |
|---|---|
| **Política e Instituições** | Funcionamento do Estado, Poderes, reforma política/eleitoral, partidos, administração pública, relações exteriores |
| **Economia e Trabalho** | Finanças públicas, tributação, crédito, mercado; emprego, sindicatos; produção rural/agropecuária |
| **Segurança e Justiça** | Polícia, criminalidade, violência, sistema prisional, legislação penal |
| **Políticas Sociais e Setoriais** | Saúde, educação, direitos humanos, assistência, cultura, infraestrutura, meio ambiente |
| **Outros** | Homenagens/efemérides sem agenda de política pública, comunicações protocolares/pessoais |

> A definição operacional completa de cada rótulo, o mapeamento ao esquema oficial e os
> **exemplos de casos-limite** estão em `taxonomia.json` (campos `definicao`,
> `esquema_senado`, `exemplos_limite`). Leia-os antes de anotar.

### Justificativa das consolidações (requisito da proposta)
- As 12 categorias finas que o app já usava (`Educação, Saúde, Economia, Cultura,
  Segurança, Meio Ambiente, Direitos Humanos, Infraestrutura, Política, Relações
  Exteriores, Trabalho, Outros`) deixariam a maioria das classes **abaixo de 20
  instâncias** nos 152 discursos — instável para métricas por classe.
- Fusões aplicadas (ver `origem_12` em `taxonomia.json`): Política+Relações Exteriores;
  Economia+Trabalho; Saúde+Educação+Direitos Humanos+Cultura+Infraestrutura+Meio
  Ambiente → "Políticas Sociais e Setoriais". Segurança e Outros permanecem isoladas.

### 2.1 Regra de decisão das classes pouco povoadas (FIXADA antes de anotar)

Gatilho definido **a priori**; apenas o ramo efetivamente acionado é registrado **depois**
da contagem do gabarito (evita parecer ajuste posterior). Anota-se os 152 nos 5 rótulos e,
sobre a contagem real de `tema_gold`:

- **Toda** classe ≥ 20 → **mantém 5 rótulos**.
- **Uma** classe em **15–19** → **aceita**; reporta a métrica por classe dessa categoria
  com ressalva explícita de instabilidade (n baixo) e enfatiza macro/ponderada.
- **Qualquer** classe **< 15**, **ou** **duas ou mais** classes < 20 → **consolida para 4
  rótulos**. A fusão segue o mesmo critério da taxonomia (ancorada no esquema do Senado e
  documentada); candidata mais provável: agrupar a **menor** classe na macrocategoria afim.

O script `scripts/classificacao/checar_gabarito.py` calcula a contagem e imprime o veredito
desta regra automaticamente.

## 3. Regras de decisão

1. **Assunto principal, não palavras isoladas.** Classifique pelo objetivo/contexto
   predominante do discurso, não pela presença de um termo. (Mesmo princípio do prompt
   do app.)
2. **Rótulo único.** Em caso de mais de um tema, escolha o **predominante**. Se houver
   empate real, use a ordem de prioridade: assunto de mérito substantivo > efeméride.
3. **Instituições vs. Segurança.** Crítica ao Judiciário como Poder → *Política e
   Instituições*. Criminalidade/polícia → *Segurança e Justiça*.
4. **Dinheiro não é sempre Economia.** Verba para hospital/escola/rodovia → *Políticas
   Sociais e Setoriais*. Tributação/juros/mercado → *Economia e Trabalho*.
5. **Protocolar/efeméride sem mérito → Outros.** Aberturas/encerramentos de sessão,
   aniversários, agradecimentos pessoais.
6. **Resumo insuficiente.** Se o `Resumo` for curto demais para decidir o mérito, marque
   *Outros* e registre na coluna `observacao` (`insuficiente`).

## 4. Anotadores — DESVIO DECLARADO em relação à proposta

> ⚠️ **Decisão metodológica FINAL (2026-06-10):** a Seção 3.6.2 da proposta previa **dupla
> anotação independente + Kappa de Cohen (κ ≥ 0,61)** com desempate por terceiro anotador.
> Esta frente é executada com **anotador único** (a pesquisadora), **igual à frente de
> geração**. A anotação é feita **integralmente pela pesquisadora**.
>
> - O **Prof. Gilton NÃO participa de nenhum trabalho de anotação**; a orientação apenas
>   **toma ciência do desvio na redação**, sem envolvimento operacional.
> - A condição de anotador único é **declarada como desvio/limitação no texto do artigo**.
>
> **Consequências, a declarar como limitação:**
> - Não há medida de concordância interanotador (sem Kappa) para a classificação.
> - A confiabilidade do gabarito repousa na consistência de um único anotador guiado por
>   este protocolo fixado a priori.
>
> **NÃO** declarar dupla anotação nem reportar Kappa — a anotação é, de fato, única. A
> coluna opcional `tema_gold_2` permanece no esquema apenas por completude, não será usada.

## 5. Procedimento operacional

1. Gerar o template: `scripts/classificacao/preparar_gabarito.py`
   → `eval/classificacao/gabarito_para_anotar.csv` (abre no Excel, UTF-8).
2. Preencher **apenas** a coluna `tema_gold` com um dos 5 rótulos (lista exata acima).
   **Anotação cega:** o arquivo **não contém** predição de nenhum sistema (nem keyword nem
   Mistral). Expor a saída de um baseline ao anotador enviesaria o gabarito contra o próprio
   sistema que ele julga — por isso a coluna de sugestão foi removida.
3. Usar `observacao` para casos-limite/dúvidas.
4. Ao terminar, salvar como `eval/classificacao/gabarito.csv` (mesmas colunas).
5. Conferência de cobertura: ≥150 discursos anotados, idealmente ≥20 por classe. Se
   alguma classe ficar abaixo, registrar e decidir consolidação adicional (Seção 2).

## 6. Estrutura do CSV do gabarito

`id_discurso, Data, Parlamentar, Partido, UF, Resumo, tema_gold, observacao`

- `tema_gold` — **anotação humana** (o que vale como verdade).
- Sem coluna de predição/sugestão: anotação cega (ver §5).
- `tema_gold_2` (opcional) — só se houver segundo anotador; habilita Kappa.
