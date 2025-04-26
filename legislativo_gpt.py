import pandas as pd
import csv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from transformers import pipeline
import xml.etree.ElementTree as ET
import requests

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
    c = canvas.Canvas(nome_arquivo, pagesize=letter)
    width, height = letter
    y_position = height - 40
    c.setFont("Helvetica", 10)

    for discurso in discursos:
        c.drawString(40, y_position, f"Autor: {discurso['NomeAutor']} ({discurso['Partido']})")
        y_position -= 20
        c.drawString(40, y_position, f"Tema: {discurso['Tema']}")
        y_position -= 20
        c.drawString(40, y_position, f"Resumo: {discurso['Resumo']}")
        y_position -= 20
        c.drawString(40, y_position, f"Texto Integral: {discurso['TextoIntegral']}")
        y_position -= 20
        c.drawString(40, y_position, f"URL Documento: {discurso['UrlTextoBinario']}")
        y_position -= 40

        if y_position < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y_position = height - 40

    c.save()

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
