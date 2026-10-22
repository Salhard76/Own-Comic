"""Costruisce data/catalogo.json leggendo i siti degli editori.
Ogni fonte e' in SOURCES: per aggiungere un editore basta una riga.
Strategie, in ordine: 1) API WooCommerce (se 'woo'), 2) sitemap + dati strutturati JSON-LD.
Se una fonte fallisce le altre proseguono; i log mostrano cosa e' successo."""
import json, re, html, gzip, time, os, datetime, urllib.request

SOURCES = [
    dict(name='Bonelli', pub='Sergio Bonelli Editore', where='Edicola',
         woo='https://www.sergiobonelli.it',
         sitemaps=['https://www.sergiobonelli.it/sitemap_index.xml', 'https://www.sergiobonelli.it/product-sitemap.xml', 'https://www.sergiobonelli.it/wp-sitemap.xml'],
         include=r'/(prodotto|product)/'),
    dict(name='Panini', pub='Panini Comics', where='Fumetteria',
         sitemaps=['https://www.panini.it/sitemap.xml', 'https://www.panini.it/sitemap_index.xml'],
         include=r'/shp_ita_it/.+\.html'),
]
MAX_NEW = 250      # pagine prodotto nuove lette per fonte a ogni giro
OUT = 'data/catalogo.json'
TODAY = datetime.date.today()
UA = {'User-Agent': 'Mozilla/5.0 (compatible; FumettiApp/1.0)', 'Accept-Language': 'it-IT,it;q=0.9', 'Accept-Encoding': 'gzip'}
MESI = {m: i + 1 for i, m in enumerate('gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre'.split())}
SKIP = re.compile(r'merchandising|abbigliament|gadget|prodotti ufficiali|t-shirt|felpe', re.I)


def get(u, t=25):
    r = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t)
    b = r.read()
    if b[:2] == b'\x1f\x8b':
        b = gzip.decompress(b)
    return b.decode('utf-8', 'replace')


def text(s):
    return html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))


def find_date(s):
    s = text(s)
    m = re.search(r'(\d{1,2})[/.](\d{1,2})[/.](20\d\d)', s)
    try:
        if m:
            return datetime.date(int(m[3]), int(m[2]), int(m[1])).isoformat()
        m = re.search(r'(\d{1,2})\s*[°º]?\s+(' + '|'.join(MESI) + r')\s*(20\d\d)?', s, re.I)
        if m:
            mo, d = MESI[m[2].lower()], int(m[1])
            if m[3]:
                return datetime.date(int(m[3]), mo, d).isoformat()
            c = [datetime.date(TODAY.year + k, mo, d) for k in (-1, 0, 1)]
            return min(c, key=lambda x: abs((x - TODAY).days)).isoformat()
        m = re.search(r'(20\d\d)-(\d\d)-(\d\d)', s)
        if m:
            return datetime.date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        pass
    return ''


def ctx_date(page):
    t = text(page)
    m = re.search(r'(data di uscita|uscita|in edicola dal|disponibile dal|data di pubblicazione|release date)', t, re.I)
    return find_date(t[m.end():m.end() + 80]) if m else ''


def split(t):
    t = html.unescape(t or '').strip()
    m = re.search(r'(?:\bn\.?|\bnumero|\bvol\.?|\bvolume|#)\s*(\d+)\b', t, re.I) or re.search(r'\s(\d{1,4})\s*$', t)
    if not m:
        return t, '', ''
    return (t[:m.start()].strip(' -–:') or t), m.group(1), t[m.end():].strip(' -–:')


def jsonld(page):
    out = []
    for m in re.finditer(r'<script[^>]+ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            st = [json.loads(m.group(1))]
        except ValueError:
            continue
        while st:
            x = st.pop()
            if isinstance(x, list):
                st += x
            elif isinstance(x, dict):
                st += x.get('@graph', []) if isinstance(x.get('@graph'), list) else []
                if 'Product' in json.dumps(x.get('@type', '')):
                    out.append(x)
    return out


def og(page, k):
    m = re.search(r'<meta[^>]+property=["\']%s["\'][^>]+content=["\']([^"\']+)' % k, page, re.I)
    return html.unescape(m.group(1)) if m else ''


def first(v):
    if isinstance(v, list):
        v = v[0] if v else ''
    return v.get('url', '') if isinstance(v, dict) else (v or '')


def make(src, name, url, cover, price, desc, isbn, date, tags=''):
    if SKIP.search(tags or ''):
        return None
    title, num, sub = split(name)
    if not title:
        return None
    label = 'Topolino' if re.search(r'topolino', name, re.I) else src['name']
    try:
        price = '%.2f' % float(str(price).replace(',', '.')) if price not in ('', None) else ''
    except ValueError:
        price = ''
    return dict(title=title, num=num, sub=sub, date=date or find_date(desc), price=price, pub=src['pub'],
                where=src['where'], cover=cover or '', isbn=isbn or '', url=url, src=label)


def via_woo(src, known):
    out = []
    for pg in range(1, 6):
        try:
            data = json.loads(get('%s/wp-json/wc/store/v1/products?per_page=100&page=%d&orderby=date&order=desc' % (src['woo'], pg)))
        except Exception as e:
            print('  [woo] pagina %d: %s' % (pg, e))
            break
        if not data:
            break
        for p in data:
            if p.get('permalink') in known:
                continue
            pr = p.get('prices', {})
            price = int(pr.get('price') or 0) / 10 ** int(pr.get('currency_minor_unit', 2)) if pr.get('price') else ''
            cats = ' '.join(c.get('name', '') for c in p.get('categories', []))
            it = make(src, p.get('name', ''), p.get('permalink', ''), (p.get('images') or [{}])[0].get('src', ''), price,
                      (p.get('short_description') or '') + ' ' + (p.get('description') or ''), '', '', cats)
            if it:
                out.append(it)
        time.sleep(0.5)
    return out


def sm_urls(u, depth=0):
    try:
        x = get(u)
    except Exception as e:
        print('  [sitemap] %s: %s' % (u, e))
        return []
    locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', x)
    if '<sitemapindex' in x and depth < 2:
        out = []
        for l in locs[:15]:
            out += sm_urls(l, depth + 1)
        return out
    return locs


def via_pages(src, known):
    urls = []
    for sm in src['sitemaps']:
        urls = [u for u in sm_urls(sm) if re.search(src['include'], u) and u not in known]
        if urls:
            break
    print('  [sitemap] pagine nuove trovate: %d' % len(urls))
    out = []
    for u in urls[:MAX_NEW]:
        try:
            pg = get(u)
        except Exception as e:
            print('  [pagina] %s: %s' % (u, e))
            continue
        ld = (jsonld(pg) or [{}])[0]
        off = ld.get('offers') or {}
        off = off[0] if isinstance(off, list) and off else off
        isbn = str(ld.get('gtin13') or ld.get('isbn') or '')
        it = make(src, ld.get('name') or og(pg, 'og:title'), u, first(ld.get('image')) or og(pg, 'og:image'),
                  (off or {}).get('price') or (off or {}).get('lowPrice') or '', ld.get('description') or '',
                  isbn if re.fullmatch(r'\d{13}', isbn) else '', find_date(str(ld.get('releaseDate') or '')) or ctx_date(pg))
        if it:
            out.append(it)
        time.sleep(0.4)
    return out


def main():
    os.makedirs('data', exist_ok=True)
    try:
        old = json.load(open(OUT, encoding='utf-8')).get('items', [])
    except Exception:
        old = []
    items = {i['url']: i for i in old if i.get('url')}
    for src in SOURCES:
        new = []
        try:
            if src.get('woo'):
                new = via_woo(src, items)
            if not new:
                new = via_pages(src, items)
        except Exception as e:
            print('[%s] errore: %s' % (src['name'], e))
        for i in new:
            items[i['url']] = i
        print('[%s] nuove voci: %d (con data: %d, con copertina: %d)' % (src['name'], len(new), sum(1 for i in new if i['date']), sum(1 for i in new if i['cover'])))
    lim = (TODAY - datetime.timedelta(days=730)).isoformat()
    keep = [i for i in items.values() if not i['date'] or i['date'] >= lim]
    keep.sort(key=lambda i: i['date'] or '0', reverse=True)
    json.dump(dict(updated=TODAY.isoformat(), items=keep[:6000]), open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('Catalogo: %d voci' % len(keep))


if __name__ == '__main__':
    main()
