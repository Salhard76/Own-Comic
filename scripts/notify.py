import json, os, datetime, urllib.request

topic = os.environ.get('NTFY_TOPIC')
if not topic:
    raise SystemExit('NTFY_TOPIC mancante: crea il secret nel repository')
try:
    d = json.load(open('data/fumetti.json', encoding='utf-8'))
except Exception as e:
    raise SystemExit('data/fumetti.json non leggibile: %s' % e)
days = int(d.get('set', {}).get('days', 3) or 3)
today = datetime.date.today()
righe = []
for i in d.get('items', []):
    if i.get('bought'):
        continue
    raw = i.get('date')
    if not raw:
        continue
    try:
        n = (datetime.date.fromisoformat(raw) - today).days
    except ValueError:
        continue
    nome = (i.get('title') or 'Fumetto') + (' n. ' + str(i['num']) if i.get('num') else '')
    dove = i.get('where') or 'edicola'
    if n == 0:
        righe.append('Esce oggi: %s (%s)' % (nome, dove))
    elif n in (1, days):
        righe.append('Tra %d %s: %s (%s)' % (n, 'giorno' if n == 1 else 'giorni', nome, dove))
righe = righe[:30]
if righe:
    req = urllib.request.Request('https://ntfy.sh/' + topic, data='\n'.join(righe).encode('utf-8'),
                                 headers={'Title': 'Fumetti in uscita', 'Tags': 'books'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
        print('\n'.join(righe))
    except Exception as e:
        print('Errore ntfy:', e)
else:
    print('Nessun avviso oggi')
