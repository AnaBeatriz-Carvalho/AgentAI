"""Taxonomia temática definitiva (10 categorias) e baseline por palavras-chave.

Fonte única de verdade para a avaliação de classificação (dimensão 4.2). Reconciliada
a partir das três listas divergentes que existiam no código, conforme o
`protocolo-anotacao-AgentAI.md` (Seção 2) e o Adendo de Metodologia:

- **8 categorias reportáveis** entram no F1 por categoria do artigo.
- **2 operacionais** (``Política/Institucional`` e ``Outros``) existem para não forçar
  rótulo indevido nas 8 (regra 4.4/4.5 do protocolo).

Este módulo é puro (stdlib), sem Streamlit/OpenAI, para poder ser importado tanto pela
aplicação (o baseline em produção) quanto pelos scripts de métrica.
"""

from __future__ import annotations

import unicodedata

CAT_POLITICA = "Política/Institucional"
CAT_OUTROS = "Outros"

# As 8 que aparecem no F1 por categoria do artigo.
CATEGORIAS_REPORTAVEIS: list[str] = [
    "Saúde",
    "Educação",
    "Infraestrutura",
    "Segurança",
    "Economia",
    "Meio Ambiente",
    "Relações Exteriores",
    "Trabalho",
]

# Taxonomia completa (ordem canônica usada em relatórios e matrizes de confusão).
CATEGORIAS: list[str] = CATEGORIAS_REPORTAVEIS + [CAT_POLITICA, CAT_OUTROS]

# Palavras-chave por categoria (baseline). Termos já sem acento/caixa — o texto de
# entrada é normalizado do mesmo modo antes da comparação. "Outros" não tem termos: é o
# fallback quando nenhuma categoria pontua. As listas seguem as definições do protocolo
# (ex.: agronegócio → Economia; previdência → Trabalho).
PALAVRAS_CHAVE: dict[str, list[str]] = {
    "Saúde": [
        "saude", "sus", "hospital", "medicament", "medico", "doenca", "vacina",
        "pandemia", "enfermidade", "clinico", "saude mental", "plano de saude",
        "epidemia", "cancer", "farmac", "enfermagem",
    ],
    "Educação": [
        "educacao", "ensino", "escola", "universidade", "professor", "aluno",
        "curriculo", "alfabetizac", "evasao", "bolsa", "academic", "creche",
        "estudante", "pedagog", "fundeb", "merenda",
    ],
    "Infraestrutura": [
        "infraestrutura", "rodovia", "ferrovia", "porto", "aeroporto", "saneamento",
        "habitacao", "moradia", "mobilidade", "transporte", "obra", "construcao",
        "telecomunicac", "pavimentac", "ponte", "abastecimento de agua",
    ],
    "Segurança": [
        "seguranca publica", "policia", "crime", "violencia", "presidio", "prisao",
        "criminalidade", "delegacia", "criminal", "forcas armadas", "defesa nacional",
        "militar", "facao", "trafico", "homicidio", "armamento",
    ],
    "Economia": [
        "economia", "imposto", "tributar", "orcamento", "inflacao", "cambio", "pib",
        "investimento", "mercado", "credito", "fiscal", "monetari", "comercio",
        "industria", "agronegocio", "agropecuaria", "tarifa", "juros", "divida publica",
    ],
    "Meio Ambiente": [
        "meio ambiente", "desmatament", "clima", "climatic", "poluic", "preservac",
        "sustentabilidade", "licenciamento ambiental", "recursos hidricos", "floresta",
        "carbono", "ambiental", "energia renovavel", "biodiversidade", "amazonia",
    ],
    "Relações Exteriores": [
        "diplomacia", "relacoes exteriores", "politica externa", "comercio exterior",
        "acordo internacional", "organismo internacional", "fronteira", "embaixada",
        "bilateral", "mercosul", "onu", "exterior", "tratado",
    ],
    "Trabalho": [
        "trabalhista", "sindicato", "reforma trabalhista", "previdencia",
        "salario minimo", "desemprego", "trabalhador", "emprego", "aposentadoria",
        "clt", "jornada", "condicoes de trabalho", "carteira assinada", "informalidade",
    ],
    CAT_POLITICA: [
        "reforma politica", "eleitoral", "eleicao", "congresso", "regimento",
        "questao de ordem", "homenagem", "mocao", "poder judiciario", "poder executivo",
        "etica parlamentar", "nomeacao", "senado", "camara", "parlamentar", "legislac",
        "constituic", "plenario", "comissao", "voto de", "requerimento", "governo",
    ],
}


def normalizar(texto: str) -> str:
    """Minúsculas + remoção de acentos (casa termos independentemente de acentuação)."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.lower()


def classificar_keyword(texto: str) -> str:
    """Baseline: retorna a categoria com mais termos casados; ``Outros`` se nenhum casa.

    Empate resolvido pela ordem de ``CATEGORIAS`` (determinístico e reprodutível).
    """
    t = normalizar(texto)
    if not t:
        return CAT_OUTROS
    melhor = CAT_OUTROS
    melhor_score = 0
    for categoria in CATEGORIAS:
        termos = PALAVRAS_CHAVE.get(categoria)
        if not termos:
            continue
        score = sum(1 for termo in termos if termo in t)
        if score > melhor_score:
            melhor_score = score
            melhor = categoria
    return melhor
