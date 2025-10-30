from pathlib import Path
from dotenv import load_dotenv
import os
from src.utils.helpers import env_path

def get_google_api_key():
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return os.getenv('GOOGLE_API_KEY')

def get_env(key: str, default=None):
    dotenv_path = env_path('.env')
    load_dotenv(dotenv_path=dotenv_path)
    return os.getenv(key, default)
