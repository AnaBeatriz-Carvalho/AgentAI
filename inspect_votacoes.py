import requests, xml.etree.ElementTree as ET, datetime
headers={'Accept':'application/xml','User-Agent':'Mozilla/5.0'}
ini=datetime.date(2025,11,15).strftime('%Y%m%d')
fim=datetime.date(2025,11,19).strftime('%Y%m%d')
url=f'https://legis.senado.leg.br/dadosabertos/plenario/votacao/orientacaoBancada/{ini}/{fim}'
print('Consultando', url)
resp=requests.get(url, headers=headers, timeout=30)
print('Status', resp.status_code)
root=ET.fromstring(resp.text)
nodes=root.findall('.//votacoes')
print('Total votacoes nodes', len(nodes))
for idx,v in enumerate(nodes[:2]):
    print('--- node', idx, '---')
    for child in list(v):
        print(child.tag, ':', (child.text or '').strip().replace('\n',' ')[:90])
codes={c.text.strip() for c in root.findall('.//codigoMateria') if c.text}
print('codigoMateria count', len(codes))
if codes:
    sample=next(iter(codes))
    det_url=f'https://legis.senado.leg.br/dadosabertos/materia/{sample}'
    print('Materia URL', det_url)
    det_resp=requests.get(det_url, headers=headers, timeout=30)
    print('Materia status', det_resp.status_code)
    if det_resp.status_code==200:
        det_root=ET.fromstring(det_resp.text)
        ementa=det_root.find('.//EmentaMateria')
        explic=det_root.find('.//ExplicacaoEmentaMateria')
        autores=[a.find('NomeAutor').text for a in det_root.findall('.//Autor') if a.find('NomeAutor') is not None]
        print('Ementa snippet', (ementa.text[:120] if ementa is not None and ementa.text else ''))
        print('Explicacao snippet', (explic.text[:120] if explic is not None and explic.text else ''))
        print('Autores', autores[:5])
