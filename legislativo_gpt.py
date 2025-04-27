import pandas as pd
import csv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from transformers import pipeline
import xml.etree.ElementTree as ET
import requests
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime
# Carrega o classificador de tema
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
    y_position = 700  # Posição inicial para o primeiro discurso

    for idx, discurso in enumerate(discursos, 1):
        if y_position < 100:  # Se chegar no fim da página, cria uma nova página
            pdf.showPage()
            y_position = 750

        # Adiciona título para cada discurso
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(50, y_position, f"Discurso {idx}")
        y_position -= 20

        # Adiciona detalhes do discurso
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, y_position, f"Autor: {discurso['NomeAutor']} ({discurso['Partido']})")
        y_position -= 15
        pdf.drawString(50, y_position, f"Tema: {discurso['Tema']}")
        y_position -= 15

        # Resumo e Texto Integral
        pdf.setFont("Helvetica", 10)
        pdf.drawString(50, y_position, f"Resumo: {discurso['Resumo']}")
        y_position -= 15
        pdf.drawString(50, y_position, f"Texto Integral: {discurso['TextoIntegral']}")
        y_position -= 30

    # Salva o PDF gerado
    pdf.save()


def buscar_discursos(data_inicio, data_fim, stop_event=None, update_progress=None):
    url = f"https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/{data_inicio}/{data_fim}"
    headers = {"Accept": "application/xml"}
    response = requests.get(url, headers=headers)

    print(f"Status HTTP: {response.status_code}")
    print(f"Conteúdo da resposta: {response.text[:500]}")

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)
            sessoes = root.findall('.//Sessoes//Sessao//Pronunciamentos//Pronunciamento')

            if not sessoes:
                print("Nenhum discurso encontrado para o intervalo de datas.")
                return []

            discursos = []
            total_discursos = len(sessoes)

            for idx, sessao in enumerate(sessoes):
                if stop_event and stop_event.is_set():
                    print("Busca interrompida pelo usuário.")
                    break

                codigo_pronunciamento = sessao.find('CodigoPronunciamento')
                tipo_uso_palavra_codigo = sessao.find('.//TipoUsoPalavra/Codigo')
                tipo_uso_palavra_descricao = sessao.find('.//TipoUsoPalavra/Descricao')
                resumo = sessao.find('Resumo')
                texto_integral = sessao.find('TextoIntegralTxt')
                url_texto_binario = sessao.find('UrlTextoBinario')
                nome_autor = sessao.find('NomeAutor')
                partido = sessao.find('Partido')

                discurso_info = {
                    'CodigoPronunciamento': codigo_pronunciamento.text if codigo_pronunciamento is not None else 'Não disponível',
                    'TipoUsoPalavra': {
                        'Codigo': tipo_uso_palavra_codigo.text if tipo_uso_palavra_codigo is not None else 'Não disponível',
                        'Descricao': tipo_uso_palavra_descricao.text if tipo_uso_palavra_descricao is not None else 'Não disponível',
                    },
                    'Resumo': resumo.text if resumo is not None else 'Não disponível',
                    'TextoIntegral': texto_integral.text if texto_integral is not None else 'Não disponível',
                    'UrlTextoBinario': url_texto_binario.text if url_texto_binario is not None else 'Não disponível',
                    'NomeAutor': nome_autor.text if nome_autor is not None else 'Não disponível',
                    'Partido': partido.text if partido is not None else 'Não disponível',
                    'Tema': classificar_tema(resumo.text) if resumo is not None else 'Não disponível'
                }

                discursos.append(discurso_info)

                # Atualiza a barra de progresso
                if update_progress:
                    update_progress.progress((idx + 1) / total_discursos)

            return discursos

        except ET.ParseError as e:
            print("Erro ao fazer o parse do XML:", e)
            print("Resposta recebida (parcial):", response.text[:500])
            return []
    else:
        print("Falha na requisição!")
        return []
