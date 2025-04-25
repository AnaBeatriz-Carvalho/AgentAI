import requests
import xml.etree.ElementTree as ET
from transformers import pipeline

# 🚀 Carrega o modelo UMA vez só
classificador = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def classificar_tema(resumo):
    # Define os possíveis temas para classificação
    temas = ["Política", "Economia", "Educação", "Saúde", "Meio Ambiente", "Tecnologia", "Segurança"]
    try:
        # Realiza a classificação
        resultado = classificador(resumo, temas)
        return resultado['labels'][0]
    except Exception as e:
        print(f"Erro ao classificar tema: {e}")
        return 'Erro na classificação'

def buscar_discursos(data_inicio, data_fim):
    url = f"https://legis.senado.leg.br/dadosabertos/plenario/lista/discursos/{data_inicio}/{data_fim}"

    headers = {
        "Accept": "application/xml"
    }

    response = requests.get(url, headers=headers)

    print(f"Status HTTP: {response.status_code}")

    if response.status_code == 200:
        try:
            root = ET.fromstring(response.content)

            discursos = []
            for sessao in root.findall('.//Sessoes//Sessao//Pronunciamentos//Pronunciamento'):
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

            return discursos

        except ET.ParseError as e:
            print("Erro ao fazer o parse do XML:", e)
            print("Resposta recebida (parcial):", response.text[:500])
            return None
    else:
        print("Falha na requisição!")
        return None

# Teste
discursos = buscar_discursos("20250301", "20250401")

if discursos:
    for i, discurso in enumerate(discursos, 1):
        print(f"Discurso {i}:")
        for key, value in discurso.items():
            print(f"{key}: {value}")
        print("="*40)
else:
    print("Não foi possível recuperar os discursos.")
