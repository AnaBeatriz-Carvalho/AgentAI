import requests, xml.etree.ElementTree as ET, datetime
headers={'Accept':'application/xml','User-Agent':'Mozilla/5.0'}
start=datetime.date(2025,9,23)
end=datetime.date(2025,11,19)
max_span=30
current=start
all_votacoes=[]
while current<=end:
    window_end=min(current+datetime.timedelta(days=max_span-1), end)
    ini=current.strftime('%Y%m%d'); fim=window_end.strftime('%Y%m%d')
    url=f'https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/{ini}/{fim}'
    resp=requests.get(url, headers=headers, timeout=40)
    if resp.status_code!=200:
        print('Falha', url, resp.status_code); current=window_end+datetime.timedelta(days=1); continue
    try:
        root=ET.fromstring(resp.text)
    except Exception as e:
        print('XML parse erro', e); current=window_end+datetime.timedelta(days=1); continue
    nodes=root.findall('.//votacoes')
    print(f'Janela {ini}-{fim}: {len(nodes)} votacoes')
    for v in nodes[:2]:
        # mostrar campos principais
        desc=(v.find('descricaoMateria').text if v.find('descricaoMateria') is not None else '')
        data=(v.find('dataInicioVotacao').text if v.find('dataInicioVotacao') is not None else '')
        codigo=(v.find('codigoMateria').text if v.find('codigoMateria') is not None else '')
        print('  Amostra -> codigoMateria:', codigo, '| dataInicio:', data, '| descricaoMateria:', desc[:90])
    all_votacoes.extend(nodes)
    current=window_end+datetime.timedelta(days=1)
print('\nTotal acumulado de votacoes:', len(all_votacoes))
# Estatísticas de presença de codigoMateria
codigos=[n.find('codigoMateria').text.strip() for n in all_votacoes if n.find('codigoMateria') is not None and n.find('codigoMateria').text]
print('Total com codigoMateria:', len(codigos), 'Distinct:', len(set(codigos)))
if codigos:
    sample=codigos[0]
    det_url=f'https://legis.senado.leg.br/dadosabertos/materia/{sample}'
    det_resp=requests.get(det_url, headers=headers, timeout=40)
    print('Detalhe materia status', det_resp.status_code, det_url)
    if det_resp.status_code==200:
        det_root=ET.fromstring(det_resp.text)
        ementa=det_root.find('.//EmentaMateria')
        explic=det_root.find('.//ExplicacaoEmentaMateria')
        print('Ementa snippet:', (ementa.text[:140] if ementa is not None and ementa.text else ''))
        print('Explicacao snippet:', (explic.text[:140] if explic is not None and explic.text else ''))
