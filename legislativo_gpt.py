import pandas as pd
import reportlab
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from transformers import pipeline
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
import streamlit as st  # <-- IMPORTANTE: Adicionado para usar st.cache_data
import streamlit as st
import threading
from streamlit.delta_generator import DeltaGenerator  # Explicitly import DeltaGenerator

# Inicializa o classificador de temas
classificador = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def classificar_tema(resumo):
    temas = [
        "Política",
        "Economia",
        "Educação",
        "Saúde",
        "Meio Ambiente",
        "Tecnologia",
        "Segurança",
    ]
    try:
        resultado = classificador(resumo, temas)
        return resultado["labels"][0]
    except Exception as e:
        print(f"Erro ao classificar tema: {e}")
        return "Erro na classificação"

def salvar_em_csv(discursos, nome_arquivo="discursos.csv"):
    if discursos:
        df = pd.DataFrame(discursos)
        df.to_csv(nome_arquivo, index=False)
    else:
        print("Nenhum dado para salvar.")

def salvar_em_pdf(discursos, nome_arquivo="relatorio_discursos.pdf"):
    # Cria o canvas do reportlab
    pdf = canvas.Canvas(nome_arquivo, pagesize=letter)
    pdf.setFont("Helvetica", 12)

    # Capa
    pdf.drawString(200, 750, "Relatório de Discursos")
    pdf.drawString(180, 730, f"Data de geração: {datetime.now().strftime('%d/%m/%Y')}")
    pdf.drawString(50, 710, "Este relatório contém os discursos coletados e classificados automaticamente.")
    pdf.showPage()

    # Conteúdo dos discursos
    y_position = 700

    for idx, discurso in enumerate(discursos, 1):
        if y_position < 100:
            pdf.showPage()
            y_position = 750

        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, f"Discurso {idx}")
        y_position -= 20

        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, y_position, f"Autor: {discurso['NomeAutor']} ({discurso['Partido']})")
        y_position -= 15
        pdf.drawString(50, y_position, f"Tema: {discurso['Tema']}")
        y_position -= 15

        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y_position, f"Resumo: {discurso['Resumo']}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Texto Integral: {discurso['TextoIntegral']}")
        y_position -= 30

    pdf.save()

@st.cache_data(show_spinner=False, hash_funcs={threading.Event: lambda _: None, DeltaGenerator: lambda _: None})
def buscar_discursos(data_inicio, data_fim, stop_event=None, _update_progress=None):
    url = f"https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/{data_inicio}/{data_fim}"
    headers = {"Accept": "application/xml"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print("Falha na requisição!")
        return []

    try:
        root = ET.fromstring(response.content)
        sessoes = root.findall('.//Sessoes//Sessao')

        if not sessoes:
            print("Nenhuma sessão encontrada para o intervalo de datas.")
            return []

        discursos = []
        total_pronunciamentos = sum(len(sessao.findall('.//Pronunciamentos//Pronunciamento')) for sessao in sessoes)
        current_idx = 0

        for sessao in sessoes:
            data_sessao = sessao.find('DataSessao').text if sessao.find('DataSessao') is not None else 'Não disponível'

            pronunciamentos = sessao.findall('.//Pronunciamentos//Pronunciamento')
            for pronunciamento in pronunciamentos:
                if stop_event and stop_event.is_set():
                    print("Busca interrompida pelo usuário.")
                    return discursos  # Retorna o que foi coletado até agora

                discurso_info = {
                    'DataSessao': data_sessao,
                    'CodigoPronunciamento': pronunciamento.findtext('CodigoPronunciamento', default='Não disponível'),
                    'TipoUsoPalavra': {
                        'Codigo': pronunciamento.findtext('.//TipoUsoPalavra/Codigo', default='Não disponível'),
                        'Descricao': pronunciamento.findtext('.//TipoUsoPalavra/Descricao', default='Não disponível'),
                    },
                    'Resumo': pronunciamento.findtext('Resumo', default='Não disponível'),
                    'TextoIntegral': pronunciamento.findtext('TextoIntegralTxt', default='Não disponível'),
                    'UrlTextoBinario': pronunciamento.findtext('UrlTextoBinario', default='Não disponível'),
                    'NomeAutor': pronunciamento.findtext('NomeAutor', default='Não disponível'),
                    'Partido': pronunciamento.findtext('Partido', default='Não disponível'),
                    'Tema': classificar_tema(pronunciamento.findtext('Resumo')) if pronunciamento.find('Resumo') is not None else 'Não disponível'
                }

                discursos.append(discurso_info)

                # Atualiza a barra de progresso (se foi passada)
                current_idx += 1
                if _update_progress:
                    _update_progress(current_idx / total_pronunciamentos)

        return discursos

    except ET.ParseError as e:
        print("Erro ao fazer o parse do XML:", e)
        print("Resposta recebida (parcial):", response.text[:500])
        return []