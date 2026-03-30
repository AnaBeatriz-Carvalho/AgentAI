from dotenv import load_dotenv
import os
from src.utils.helpers import env_path

DEFAULT_LOCAL_LLM_BASE_URL = "http://localhost:1234/v1"
DEFAULT_LOCAL_LLM_API_KEY = "lm-studio"
DEFAULT_LOCAL_LLM_MODEL = "qwen3-vl-4b"

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
