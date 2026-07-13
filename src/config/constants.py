"""Constantes centralizadas do projeto."""

# URLs da API do Senado
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"
SENADO_API_DISCURSOS = f"{SENADO_API_BASE}/plenario/lista/discursos"
SENADO_API_VOTACOES = f"{SENADO_API_BASE}/plenario/votacao/orientacaoBancada"
SENADO_API_MATERIAS = f"{SENADO_API_BASE}/votacao"
SENADO_API_MATERIA_DETALHES = f"{SENADO_API_BASE}/materia"  # DEPRECATED na API; ver SENADO_API_PROCESSO
# Endpoint moderno de Processos Legislativos (substitui /materia/*): traz ementa,
# autoria, situação atual, tipo de documento e link para o texto integral.
SENADO_API_PROCESSO = f"{SENADO_API_BASE}/processo"
# Texto integral de um pronunciamento (formato texto plano), por codigoPronunciamento.
SENADO_API_TEXTO_INTEGRAL = f"{SENADO_API_BASE}/discurso/texto-integral"

# Headers para requisições
SENADO_HEADERS = {
    "Accept": "application/xml",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Variante para os endpoints consumidos em JSON (votações/processos).
SENADO_HEADERS_JSON = {
    "Accept": "application/json",
    "User-Agent": SENADO_HEADERS["User-Agent"],
}

# Temas de classificação
TEMAS_DEFINIDOS = [
    "Educação", "Saúde", "Economia", "Cultura", "Segurança",
    "Meio Ambiente", "Direitos Humanos", "Infraestrutura",
    "Política", "Relações Exteriores", "Trabalho", "Outros"
]

# Timeouts
REQUEST_TIMEOUT = 30  # segundos
LLM_TIMEOUT = 60  # segundos

# Cache TTL (em segundos)
CACHE_TTL_DISCURSOS = 86400  # 24 horas
CACHE_TTL_VOTACOES = 3600    # 1 hora

# Limites
MAX_PERIODO_DIAS = 30
MAX_ATORES_MENCIONADOS = 5
MAX_TEMA_LENGTH = 5
MAX_RESUMO_LENGTH = 2
MAX_PARLAMENTARES_TOP = 7
MAX_TEMAS_DISPLAY = 10

# Orçamento de contexto enviado ao LLM nos chats (evita estourar a janela do modelo).
# Defaults dimensionados para um modelo carregado com n_ctx = 4096. Se você carregar o
# modelo no LM Studio com um contexto maior (ex.: 8192/16384), pode aumentar estes valores
# para respostas mais ricas (mais fontes citáveis).
MAX_FONTES_PROMPT = 15            # nº de discursos/votos injetados como fontes no prompt
MAX_CHARS_CONTEXTO_PROMPT = 7000  # corte final de segurança do bloco de contexto

# Nomes de colunas
COL_ID_DISCURSO = "id_discurso"
COL_DATA = "Data"
COL_PARLAMENTAR = "Parlamentar"
COL_PARTIDO = "Partido"
COL_UF = "UF"
COL_RESUMO = "Resumo"
COL_TEMA = "Tema"
