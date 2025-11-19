from pathlib import Path
from dotenv import load_dotenv
import os
from src.utils.helpers import env_path

DEFAULT_GEMINI_MODEL_DISCURSOS = 'gemini-2.0-flash'
DEFAULT_GEMINI_MODEL_VOTACOES = 'gemini-2.5-pro'

def get_google_api_key():
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return os.getenv('GOOGLE_API_KEY')

def get_env(key: str, default=None):
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return os.getenv(key, default)

def get_gemini_models():
    """Retorna dicionário com modelos configurados para discursos e votações.

    Variáveis suportadas em .env:
      GEMINI_MODEL_DISCURSOS
      GEMINI_MODEL_VOTACOES
    Se ausentes, usa defaults.
    """
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return {
        'discursos': os.getenv('GEMINI_MODEL_DISCURSOS', DEFAULT_GEMINI_MODEL_DISCURSOS),
        'votacoes': os.getenv('GEMINI_MODEL_VOTACOES', DEFAULT_GEMINI_MODEL_VOTACOES)
    }
