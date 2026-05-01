"""Constantes centralizadas do projeto."""

# URLs da API do Senado
SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"
SENADO_API_DISCURSOS = f"{SENADO_API_BASE}/plenario/lista/discursos"
SENADO_API_VOTACOES = f"{SENADO_API_BASE}/plenario/votacao/orientacaoBancada"
SENADO_API_MATERIAS = f"{SENADO_API_BASE}/votacao"
SENADO_API_MATERIA_DETALHES = f"{SENADO_API_BASE}/materia"

# Headers para requisições
SENADO_HEADERS = {
    "Accept": "application/xml",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
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

# Nomes de colunas
COL_DATA = "Data"
COL_PARLAMENTAR = "Parlamentar"
COL_PARTIDO = "Partido"
COL_UF = "UF"
COL_RESUMO = "Resumo"
COL_TEMA = "Tema"
