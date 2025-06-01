import google.generativeai as genai
import os
from dotenv import load_dotenv
import streamlit as st

def configurar_agente(model_name='gemini-1.5-flash'):
    """
    Configura o agente Gemini com a chave de API.
    
    Args:
        model_name (str): Nome do modelo Gemini a ser usado (padrão: gemini-1.5-flash).
    
    Returns:
        genai.GenerativeModel: Modelo configurado do Gemini.
    """
    try:
        # Carrega o arquivo .env
        load_dotenv()
        
        # Carrega a chave de API
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("Chave de API do Gemini não encontrada.")
        
        # Configura a API
        genai.configure(api_key=api_key)
        
        # Inicializa o modelo
        model = genai.GenerativeModel(model_name)
        
        return model
    except Exception as e:
        raise Exception(f"Erro ao configurar o agente Gemini: {e}")