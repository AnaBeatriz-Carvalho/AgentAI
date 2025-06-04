import joblib
import pandas as pd

# Carrega o classificador
modelo = joblib.load("classificador_tema.pkl")

def classificar_tema_discursos(df):
    """
    Classifica os discursos em temas.

    Args:
        df (pd.DataFrame): DataFrame com a coluna 'TextoCompleto'.

    Returns:
        pd.DataFrame: DataFrame com uma nova coluna 'TemaPrevisto'.
    """
    if 'TextoCompleto' not in df.columns:
        raise ValueError("O DataFrame deve conter a coluna 'TextoCompleto'.")

    df['TemaPrevisto'] = modelo.predict(df['TextoCompleto'].fillna(""))
    return df