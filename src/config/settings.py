from dotenv import load_dotenv
import os
from src.utils.helpers import env_path

DEFAULT_LOCAL_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LOCAL_LLM_API_KEY = "lm-studio"
DEFAULT_LOCAL_LLM_MODEL = "mistralai/mistral-7b-instruct-v0.3"

# --- Defaults do RAG ---
DEFAULT_RAG_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_RAG_CHUNK_SIZE = 400
DEFAULT_RAG_CHUNK_OVERLAP = 64
DEFAULT_RAG_TOP_K = 5
DEFAULT_RAG_INDEX_PATH = "./vectorstore/discursos.faiss"
DEFAULT_RAG_META_PATH = "./vectorstore/discursos_meta.parquet"

def get_env(key: str, default=None):
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return os.getenv(key, default)


def get_local_llm_config() -> dict:
    """Config do LLM local (OpenAI-compatível) via .env."""
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return {
        "base_url": os.getenv("LOCAL_LLM_BASE_URL", DEFAULT_LOCAL_LLM_BASE_URL),
        "api_key": os.getenv("LOCAL_LLM_API_KEY", DEFAULT_LOCAL_LLM_API_KEY),
        "model": os.getenv("LOCAL_LLM_MODEL", DEFAULT_LOCAL_LLM_MODEL),
    }


def _get_int(key: str, default: int) -> int:
    """Lê uma variável de ambiente inteira, caindo no default se ausente/inválida."""
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def get_rag_config() -> dict:
    """Config do RAG (modelo de embedding, chunking e caminhos do índice) via .env."""
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return {
        "embedding_model": os.getenv("RAG_EMBEDDING_MODEL", DEFAULT_RAG_EMBEDDING_MODEL),
        "chunk_size": _get_int("RAG_CHUNK_SIZE", DEFAULT_RAG_CHUNK_SIZE),
        "chunk_overlap": _get_int("RAG_CHUNK_OVERLAP", DEFAULT_RAG_CHUNK_OVERLAP),
        "top_k": _get_int("RAG_TOP_K", DEFAULT_RAG_TOP_K),
        "index_path": os.getenv("RAG_INDEX_PATH", DEFAULT_RAG_INDEX_PATH),
        "meta_path": os.getenv("RAG_META_PATH", DEFAULT_RAG_META_PATH),
    }
