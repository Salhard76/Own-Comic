"""Catalogo uscite Bonelli + Panini.
Legge le stesse liste prodotto che consulti a mano e salva data/catalogo.json.
Per cambiare cosa viene letto basta modificare SOURCES."""
import json, re, html, gzip, time, os, datetime, unicodedata, urllib.request
from urllib.parse import urljoin, quote

TODAY = datetime.date.today()
OUT = 'data/catalogo.json'
PAUSE = 0.8
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'it-IT,it;q=0.9', 'Accept-Encoding': 'gzip'}
B = 'https://www.sergiobonelli.it'
P = 'https://www.panini.it/shp_ita_it/fumetti/'
PAN0 = 'https://www.panini.it/shp_ita_it/'
# Bonelli: pagine 2+ con ?paged=N (36 prodotti per pagina, dal piu' recente). Pagine "ULTIME USCITE" dei personaggi principali.
CHARS = ['tex', 'zagor', 'mister-no', 'martin-mystere', 'dylan-dog', 'nathan-never', 'julia', 'dampyr', 'dragonero']
# (fonte, indirizzo, dove si compra, pagine massime, linea, tipo di paginazione)
SOURCES = [
    ('Bonelli', B + '/categoria-prodotto/prossimamente/', 'Edicola', 2, 'Bonelli', 'paged'),
    ('Bonelli', B + '/categoria-prodotto/fumetti/', 'Edicola', 2, 'Bonelli', 'paged'),
] + [('Bonelli', B + '/categoria-prodotto/fumetti/?filter_personaggio=' + c, 'Edicola', 1, 'Bonelli', 'paged') for c in CHARS]
# Panini: ogni categoria letta due volte: con il filtro predefinito (acquistabili) e senza (include le uscite non ancora acquistabili)
for _path, _where, _line in [
        ('in-edicola/marvel.html', 'Edicola', 'Marvel'), ('in-edicola/disney.html', 'Edicola', 'Disney'),
        ('in-edicola/dc.html', 'Edicola', 'DC'), ('in-edicola/panini-comics.html', 'Edicola', 'Panini Comics'),
        ('panini-disney/tipologia/topolino-settimanale.html', 'Edicola', 'Disney'),
        ('marvel.html', 'Fumetteria', 'Marvel'), ('dc.html', 'Fumetteria', 'DC'), ('panini-disney.html', 'Fumetteria', 'Disney')]:
    SOURCES += [('Panini', P + _path, _where, 3, _line, 'q'), ('Panini', P + _path, _where, 2, _line, 'skip')]
PRICE = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*€')


def fetch(u):
    for k in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)
            b = r.read()
            if b[:2] == b'\x1f\x8b':
                b = gzip.decompress(b)
            return b.decode('utf-8', 'replace')
        except Exception as e:
            print('   errore %s: %s' % (u, e))
            time.sleep(2)
    return None


def attrs(s):
    return {k.lower(): html.unescape(a or b) for k, a, b in re.findall(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', s)}


def first_img(h):
    m = re.search(r'<img\b([^>]*)>', h, re.I | re.S)
    if not m:
        return '', ''
    a = attrs(m.group(1))
    for k in ('data-src', 'data-lazy-src', 'data-original', 'src'):
        v = a.get(k, '')
        if v and not v.startswith('data:'):
            return v, a.get('alt', '')
    ss = a.get('srcset') or a.get('data-srcset', '')
    return (ss.split()[0] if ss else ''), a.get('alt', '')


def clean(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def lines(s):
    return [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', s)).split('\n') if l.strip()]


def mkdate(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return ''


def money(m):
    return m.group(1).replace('.', '').replace(',', '.') if m else ''


def segments(page, url_re, base):
    """Un elemento per ogni link prodotto che contiene un'immagine (cioe' la scheda in elenco, non il menu)."""
    starts, seen = [], set()
    for m in re.finditer(r'<a\b([^>]*)>(.*?)</a>', page, re.S | re.I):
        h = attrs(m.group(1)).get('href', '')
        if not h:
            continue
        h = urljoin(base, h).split('#')[0]
        if re.search(url_re, h) and '<img' in m.group(2).lower() and h not in seen:
            seen.add(h)
            starts.append((m.start(), h, m.group(2)))
    out = []
    for i, (pos, h, inner) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else pos + 4000
        out.append((h, inner, page[pos:min(end, pos + 4000)]))
    return out


def parse_bonelli(page, where, line):
    out = []
    for url, inner, chunk in segments(page, r'/prodotto/', B):
        img, alt = first_img(inner)
        L = lines(chunk)
        txt = ' '.join(L)
        m = re.search(r'Uscita:?\s*(\d{1,2})/(\d{1,2})/(\d{4})', txt)
        date = mkdate(m[3], m[2], m[1]) if m else ''
        idx = next((i for i, l in enumerate(L) if 'Uscita' in l), None)
        pre = [l for l in (L[:idx] if idx is not None else []) if not l.isupper() and len(l) > 2]
        lab = (pre[-2] + ' ' + pre[-1]) if len(pre) > 1 and pre[-2] in ('Libri', 'Albi', 'Variant', 'Esclusive') else (pre[-1] if pre else '')
        story = alt
        if idx is not None:
            j = idx + 1
            if j < len(L) and re.fullmatch(r'[\d/ ]+', L[j]):
                j += 1
            if j < len(L) and not PRICE.search(L[j]):
                story = L[j]
        nm = re.search(r'\bn\.?\s*0*(\d+)\s*$', lab)
        num = nm.group(1) if nm else ''
        series = re.sub(r'^(Libri|Albi)\s+', '', lab[:nm.start()] if nm else lab).strip()
        if num and series and series.lower() != 'vari':
            title, sub = series, (re.sub(r'^' + re.escape(series) + r'[\s.:\-–]+', '', story) or story)
        else:
            title, sub, num = (story or series), '', ''
        if not title:
            continue
        out.append(dict(title=title, num=num, sub=sub, date=date, price=money(PRICE.search(txt)), pub='Sergio Bonelli Editore',
                        where='Libreria' if lab.startswith('Libri') else where, cover=img, isbn='', url=url, src='Bonelli',
                        line=line, type='serie' if num else 'oneshot'))
    return out


def parse_panini(page, where, line):
    out = []
    for url, inner, chunk in segments(page, r'-it\d\d\.html', 'https://www.panini.it/'):
        img, alt = first_img(inner)
        if 'placeholder' in img:
            img = ''
        m = re.search(r'<h\d[^>]*>\s*<a[^>]*>(.*?)</a>', chunk, re.S | re.I)
        name = clean(m.group(1)) if m else re.sub(r'^[^_]*_', '', alt).strip()
        if not name:
            continue
        txt = clean(chunk)
        d = re.search(r'\b(\d{2})/(\d{2})/(\d{2})\b', txt)
        date = mkdate(2000 + int(d[3]), d[2], d[1]) if d else ''
        pm = re.search(r'Prezzo predefinito\s*(\d{1,3}(?:\.\d{3})*,\d{2})', txt) or PRICE.search(txt)
        nm = re.search(r'\bn\.?\s*0*(\d+)\s*$', name) or re.search(r'\s0*(\d{1,4})\s*$', name)
        title, num = (name[:nm.start()].strip(' -–:') or name, nm.group(1)) if nm else (name, '')
        var = 'isbnv' in url.lower() or re.search(r'variant', name, re.I)
        out.append(dict(title=title, num=num, sub='Variant' if var else '', date=date, price=money(pm), pub='Panini Comics',
                        where=where, cover=img, isbn='', url=url, src='Topolino' if title.lower().startswith('topolino') else 'Panini',
                        line=line, type='serie' if num else 'oneshot'))
    return out


def page_url(base, n, kind):
    if kind == 'sq':
        return base + ('' if n == 1 else '&p=%d' % n)
    if kind == 'paged':
        return base if n == 1 else base + ('&' if '?' in base else '?') + 'paged=%d' % n
    if kind == 'skip':
        return base + '?skip_default_filters=true' + ('' if n == 1 else '&p=%d' % n)
    return base if n == 1 else base + '?p=%d&pnn_is_saleable=1' % n


def scrape(name, base, where, maxp, line, kind, run, items, flt=None):
    got, dates = 0, []
    for n in range(1, maxp + 1):
        u = page_url(base, n, kind)
        pg = fetch(u)
        if pg is None:
            break
        found = (parse_bonelli if name == 'Bonelli' else parse_panini)(pg, where, line)
        if flt:
            found = [i for i in found if flt(i)]
        if not found:
            print('  [%s] pagina %d senza prodotti (%s)' % (name, n, u))
            if n == 1:
                open('data/debug-%s.txt' % name.lower(), 'w', encoding='utf-8').write(
                    '== %s\nlunghezza %d, link /prodotto/: %d, link -it08: %d\n%s\n' % (u, len(pg), pg.count('/prodotto/'), len(re.findall(r'-it\d\d\.html', pg)), pg[:1500]))
            break
        dates += [i['date'] for i in found if i['date']]
        fresh = [i for i in found if i['url'] not in run]
        for i in fresh:
            run.add(i['url'])
            items[i['url']] = i
        got += len(fresh)
        if not fresh:
            break
        time.sleep(PAUSE)
    ds = sorted(dates)
    print('[%s] %s [%s] -> %d nuove (date %s / %s)' % (name, base.replace('https://', '')[:80], kind, got, ds[0] if ds else '-', ds[-1] if ds else '-'))


def nzs(t):
    t = unicodedata.normalize('NFD', (t or '').lower())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in t if unicodedata.category(c) != 'Mn')).strip()


def read_lista():
    """Righe 'Titolo | fonte | numero' da scripts/lista.txt, piu' i titoli della tua lista sincronizzata (se c'e')."""
    out = []
    try:
        for l in open('scripts/lista.txt', encoding='utf-8').read().splitlines():
            l = l.split('#')[0].strip()
            if l:
                p = [x.strip() for x in l.split('|')]
                out.append((p[0], p[1].lower() if len(p) > 1 and p[1] else '*', int(p[2]) if len(p) > 2 and p[2].isdigit() else 0))
    except Exception:
        pass
    try:
        for i in json.load(open('data/fumetti.json', encoding='utf-8')).get('items', []):
            t = (i.get('title') or '').strip()
            if t and nzs(t) not in [nzs(x[0]) for x in out]:
                out.append((t, '*', 0))
    except Exception:
        pass
    return out[:40]


def make_filter(title, start):
    w = nzs(title).split()
    def f(i):
        h = nzs(i['title'] + ' ' + i['sub'])
        if not all(x in h.split() or x in h for x in w):
            return False
        return not start or not i['num'] or (i['num'].isdigit() and int(i['num']) >= start)
    return f


def main():
    os.makedirs('data', exist_ok=True)
    try:
        old = json.load(open(OUT, encoding='utf-8')).get('items', [])
    except Exception:
        old = []
    items = {i['url']: i for i in old if i.get('url')}
    run = set()
    for name, base, where, maxp, line, kind in SOURCES:
        scrape(name, base, where, maxp, line, kind, run, items)
    entries = read_lista()
    print('Lista di ricerca: %d titoli' % len(entries))
    for t, src, st in entries:
        f = make_filter(t, st)
        if src in ('*', 'panini', 'marvel', 'dc', 'disney', 'topolino'):
            scrape('Panini', PAN0 + 'catalogsearch/result/?q=' + quote(t) + '&product_list_order=release_date&product_list_dir=desc', 'Edicola', 2, 'Lista', 'sq', run, items, f)
        if src in ('*', 'bonelli'):
            scrape('Bonelli', B + '/categoria-prodotto/fumetti/?filter_personaggio=' + nzs(t).replace(' ', '-'), 'Edicola', 2, 'Lista', 'paged', run, items, f)
    lim = (TODAY - datetime.timedelta(days=400)).isoformat()
    keep = [i for i in items.values() if not i['date'] or i['date'] >= lim]
    keep.sort(key=lambda i: i['date'] or '0', reverse=True)
    json.dump(dict(updated=TODAY.isoformat(), watch=[e[0] for e in entries], items=keep[:6000]), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('Catalogo: %d voci (Bonelli %d, Panini %d, Topolino %d)' % tuple([len(keep)] + [sum(1 for i in keep if i['src'] == k) for k in ('Bonelli', 'Panini', 'Topolino')]))


if __name__ == '__main__':
    main()
