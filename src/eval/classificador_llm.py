"""Classificador temático via LLM local com Few-Shot Learning (dimensão 4.2, etapa 5).

Classifica o ``Resumo`` de um discurso em uma das 10 categorias definitivas
(`src.eval.categorias`) usando um LLM local servido por API OpenAI-compatível (LM Studio).
Ao contrário do prompt zero-shot que já existia no app, aqui o prompt traz **exemplos
rotulados** (few-shot) e as **regras de decisão do protocolo de anotação** (tema dominante,
desempate, não forçar institucional nas 8 reportáveis), para uma comparação justa contra o
gabarito humano.

Design aberto a múltiplos modelos (Mistral/Gemma/Qwen/Jurema): ``modelo`` e ``client`` são
injetáveis; o resultado é persistido por (discurso, modelo) em ``classificacao_llm``. Isso
atende à sugestão dos revisores de comparar mais de um modelo local sem reescrever nada.

Testável sem LM Studio: injete um ``client`` fake em ``classificar_llm``.

Reprodutibilidade: ``temperature=0`` e ``PROMPT_VERSAO`` versionado; os exemplos few-shot
abaixo são **demonstrações ilustrativas da tarefa** (não são discursos reais do corpus) e,
por isso, não têm interseção com o gabarito — evita vazamento (data leakage).
"""

from __future__ import annotations

from typing import Optional

from src.eval.categorias import CATEGORIAS, CAT_OUTROS, normalizar

# Versão do prompt/few-shot: registrada junto de cada predição para rastrear mudanças.
PROMPT_VERSAO = "fewshot-v1"

# Exemplos few-shot (ilustrativos da TAREFA — não são discursos reais; sem overlap com o
# gabarito). Cobrem casos das regras do protocolo, incluindo desempate e institucional.
_EXEMPLOS: list[tuple[str, str]] = [
    ("Defesa da ampliação de leitos de UTI no SUS e da reposição de estoques de "
     "medicamentos oncológicos na rede pública.", "Saúde"),
    ("Cobrança por mais recursos para a educação básica e crítica ao índice de evasão "
     "escolar no ensino médio das redes estaduais.", "Educação"),
    ("Pedido de retomada das obras de duplicação da rodovia federal e de melhoria do "
     "saneamento básico nos municípios do interior.", "Infraestrutura"),
    ("Discussão sobre o aumento da criminalidade violenta e proposta de reforço ao "
     "policiamento ostensivo e ao sistema prisional.", "Segurança"),
    ("Análise dos impactos da reforma tributária sobre a arrecadação e defesa de medidas "
     "de controle da inflação e do déficit fiscal.", "Economia"),
    ("Denúncia do avanço do desmatamento na Amazônia e defesa de metas de redução de "
     "emissões de carbono e de licenciamento ambiental rigoroso.", "Meio Ambiente"),
    ("Comentário sobre acordo comercial bilateral e sobre a atuação do Brasil em "
     "organismos internacionais na questão das fronteiras.", "Relações Exteriores"),
    ("Defesa da valorização do salário mínimo, crítica à reforma trabalhista e apoio à "
     "pauta dos sindicatos sobre condições de trabalho.", "Trabalho"),
    ("Homenagem a personalidade falecida e registro de moção de pesar, com questão de "
     "ordem sobre o regimento interno da sessão.", "Política/Institucional"),
    ("Discussão sobre a reforma do sistema eleitoral e as regras de funcionamento do "
     "Congresso Nacional na relação entre os poderes.", "Política/Institucional"),
    # Desempate (regra 4.3): usa a crise da saúde só como mote, mas o PEDIDO é educacional.
    ("Aproveita a repercussão da crise hospitalar para pedir mais verba às universidades "
     "e bolsas de pesquisa científica.", "Educação"),
    # Fora das 9 (regra 4.5): esporte/cultura sem enquadramento nas demais.
    ("Celebração da conquista de medalha por atleta brasileiro e registro de evento "
     "cultural regional de música e artesanato.", CAT_OUTROS),
]

_CATS_STR = ", ".join(CATEGORIAS)


def _bloco_exemplos() -> str:
    linhas = []
    for texto, cat in _EXEMPLOS:
        linhas.append(f'Discurso: "{texto}"\nCategoria: {cat}')
    return "\n\n".join(linhas)


def construir_prompt(resumo: str) -> str:
    """Monta o prompt few-shot para classificar um resumo em uma das 10 categorias."""
    return f"""Você classifica discursos de senadores brasileiros em EXATAMENTE UMA categoria temática.

Categorias válidas (responda com uma delas, escrita exatamente assim):
{_CATS_STR}

Regras (nesta ordem):
1. Baseie-se no ASSUNTO PREDOMINANTE do discurso, não em uma palavra isolada.
2. Se houver mais de um tema, escolha o que ocupa a maior parte do conteúdo.
3. Desempate: escolha o tema sobre o qual há uma proposta, crítica ou pedido concreto.
4. Conteúdo sobre o funcionamento da política/Estado em si (homenagem, regimento, processo
   eleitoral, relação entre poderes, questão de ordem) é "Política/Institucional" — não force
   em Economia/Segurança só porque a palavra apareceu.
5. Se não couber em nenhuma das 9 categorias temáticas, responda "Outros".

Responda SOMENTE com o nome exato da categoria, sem explicação, sem pontuação extra.

Exemplos:

{_bloco_exemplos()}

Agora classifique:
Discurso: "{resumo}"
Categoria:"""


# Índice de categorias normalizadas → rótulo canônico, para casar a resposta do modelo.
_CANON = {normalizar(c): c for c in CATEGORIAS}


def _mapear_categoria(resposta: str) -> str:
    """Converte a resposta livre do modelo no rótulo canônico; ``Outros`` se não casar."""
    if not resposta:
        return CAT_OUTROS
    norm = normalizar(resposta).strip().strip(".").strip()
    if norm in _CANON:
        return _CANON[norm]
    # Casa por substring (modelo às vezes devolve "Categoria: Saúde." ou frase curta).
    for chave, canonico in _CANON.items():
        if chave and chave in norm:
            return canonico
    return CAT_OUTROS


def _client_padrao():
    """Cria o client OpenAI-compatível a partir do .env (import tardio p/ testabilidade)."""
    from openai import OpenAI
    from src.config.settings import get_local_llm_config
    cfg = get_local_llm_config()
    return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"]), cfg["model"]


def classificar_llm(
    resumo: str,
    modelo: Optional[str] = None,
    client=None,
    temperature: float = 0.0,
) -> str:
    """Classifica um resumo via LLM few-shot. Retorna uma das 10 categorias canônicas.

    `client`/`modelo` injetáveis (default: LM Studio via .env). Robusto: erro de API ou
    resposta fora do conjunto cai em ``Outros`` sem levantar exceção.
    """
    if not resumo or not resumo.strip():
        return CAT_OUTROS

    modelo_efetivo = modelo
    if client is None:
        client, modelo_default = _client_padrao()
        modelo_efetivo = modelo or modelo_default

    prompt = construir_prompt(resumo)
    try:
        resp = client.chat.completions.create(
            model=modelo_efetivo,
            messages=[
                {"role": "system", "content": "Você responde apenas com o nome exato de uma categoria."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        conteudo = (resp.choices[0].message.content or "").strip()
    except Exception:
        return CAT_OUTROS

    return _mapear_categoria(conteudo)
