"""Calisan sunucuya karsi uctan uca API taramasi (demo sunucu, port 5050).

Normal, uc durum ve bozuk girdilerle her ucu cagirir; 5xx hata, istisna ya da
yavas cevap arar. Canli sunucuya karsi CALISTIRMAYIN (ayar/kural yazar).

    python tests/api_duman.py [http://localhost:5050]
"""

import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request

B = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5050'
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
SONUC = []


def istek(m, p, body=None, raw=False, beklenen=(200,)):
    r = urllib.request.Request(B + p, method=m, data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type': 'application/json'})
    t = time.time()
    try:
        with op.open(r, timeout=60) as f:
            d = f.read()
            kod = f.status
    except urllib.error.HTTPError as e:
        d, kod = e.read(), e.code
    except Exception as e:                       # baglanti cevapsiz kapandi vb.
        d, kod = repr(e).encode(), 0
    sure = time.time() - t
    ok = kod in beklenen
    SONUC.append((ok and sure < 5, m, p, kod, round(sure, 2)))
    if not ok or sure >= 5:
        print(f'  !! {m} {p} -> {kod} ({sure:.2f}s) {d[:200]!r}')
    if raw:
        return d
    try:
        return json.loads(d) if d else None
    except ValueError:
        return d


def main():
    istek('POST', '/api/login', {'username': 'admin', 'password': 'yanlis'}, beklenen=(401,))
    istek('POST', '/api/login', {'username': 'admin', 'password': 'Aa123456'})
    meta = istek('GET', '/api/meta')
    boyutlar = [d['key'] for d in meta['dimensions']]
    olculer = [m['key'] for m in meta['measures']]

    # --- her boyut x her olcu
    for b in boyutlar:
        istek('POST', '/api/analiz/sorgu', {'group_by': [b], 'measures': olculer, 'limit': 50})
    for yon in ['SATIS_NET', 'SATIS', 'ALIS_NET', 'ALIS', 'TUMU']:
        istek('POST', '/api/analiz/sorgu', {'direction': yon, 'group_by': ['brand', 'month'], 'measures': ['net_tl', 'margin']})
    # pivot her zaman boyutuyla
    for p in ['day', 'week', 'month', 'quarter', 'year', 'weekday', 'brand', 'client', 'item']:
        istek('POST', '/api/analiz/sorgu', {'group_by': ['category'], 'pivot_by': p, 'measures': ['qty'], 'date_from': '2025-01-01'})
    # 4 kirilim
    istek('POST', '/api/analiz/sorgu', {'group_by': ['brand', 'category', 'salesman', 'city'], 'measures': ['net_tl']})
    # uc durumlar
    istek('POST', '/api/analiz/sorgu', {'date_from': '2010-01-01', 'date_to': '2010-12-31', 'group_by': ['brand'], 'measures': ['margin']})
    istek('POST', '/api/analiz/sorgu', {'date_from': '2026-12-31', 'date_to': '2020-01-01', 'measures': ['net_tl']})
    istek('POST', '/api/analiz/sorgu', {'search': 'çğıöşü İ %_\'"', 'measures': ['net_tl']})
    istek('POST', '/api/analiz/sorgu', {'filters': {'brand': {'not': True, 'values': ['Dell']}}, 'measures': ['net_tl']})
    istek('POST', '/api/analiz/sorgu', {'filters': {'brand': []}, 'measures': ['net_tl']})
    istek('POST', '/api/analiz/sorgu', {'group_by': ['a', 'b', 'c', 'd', 'e']}, beklenen=(400,))
    istek('POST', '/api/analiz/sorgu', {'date_from': 'dun'}, beklenen=(400,))
    istek('POST', '/api/analiz/sorgu', {'direction': 'X'}, beklenen=(400,))
    istek('POST', '/api/analiz/sorgu', {'group_by': ['brand'], 'measures': []})
    istek('POST', '/api/analiz/sorgu', {'group_by': ['brand'], 'sort': {'key': 'olmayan'}, 'measures': ['qty']})
    istek('POST', '/api/analiz/sorgu', {'group_by': ['brand'], 'pivot_by': 'brand', 'measures': ['qty']})

    # --- satirlar
    for k in ['date', 'stock_age', 'net_tl', 'client', 'olmayan; DROP']:
        istek('POST', '/api/analiz/satirlar', {'sort': {'key': k, 'desc': False}, 'limit': 50})
    istek('POST', '/api/analiz/satirlar', {'limit': 999999, 'offset': -5})
    istek('POST', '/api/analiz/satirlar', {'limit': 'abc'}, beklenen=(400, 500))

    istek('POST', '/api/analiz/secenekler', {})
    istek('POST', '/api/analiz/secenekler', {'date_from': '2010-01-01', 'date_to': '2010-02-01'})
    for b in ['client', 'item', 'client_group', 'item_code']:
        istek('GET', f'/api/ara?boyut={b}&q=a')
    istek('GET', '/api/ara?boyut=brand&q=a', beklenen=(400,))
    istek('GET', '/api/ara?boyut=client&q=%25%27')

    # --- genel bakis / stok / donem
    for k in ['previous', 'year', 'none']:
        istek('POST', '/api/genel-bakis', {'compare': k})
    for g in ['day', 'week', 'month', 'quarter', 'year']:
        istek('POST', '/api/genel-bakis', {'granularity': g, 'date_from': '2016-01-01'})
    istek('POST', '/api/genel-bakis', {'date_from': '2016-02-29', 'date_to': '2016-02-29', 'compare': 'year'})
    istek('POST', '/api/genel-bakis', {'measure': 'net_usd'})
    istek('POST', '/api/stok', {})
    istek('POST', '/api/stok', {'as_of': '2015-01-01'})
    istek('POST', '/api/stok', {'only_in_stock': False, 'search': 'dell', 'filters': {'brand': ['Dell']}, 'sort': {'key': 'days_since_move'}})
    istek('POST', '/api/stok', {'velocity_days': 0})
    for g in ['category', 'brand', 'kind', 'revenue_type']:
        istek('POST', '/api/donem-raporu', {'date_from': '2026-09-01', 'date_to': '2026-09-30', 'group_by': g})
    istek('POST', '/api/donem-raporu', {'group_by': 'client'}, beklenen=(400,))
    istek('POST', '/api/donem-raporu', {'date_from': '2010-01-01', 'date_to': '2010-01-31'})

    # --- excel
    for tur, govde in [('sorgu', {'request': {'group_by': ['brand'], 'pivot_by': 'year', 'measures': ['net_tl']}}),
                       ('satirlar', {'request': {'date_from': '2026-09-01'}}), ('stok', {'request': {}}),
                       ('donem', {'request': {'date_from': '2026-09-01', 'date_to': '2026-09-30'}}),
                       ('sorgu', {'request': {'date_from': '2010-01-01', 'date_to': '2010-02-01', 'group_by': ['brand']}})]:
        d = istek('POST', f'/api/export/{tur}', govde, raw=True)
        if not (isinstance(d, bytes) and d[:2] == b'PK'):
            print(f'  !! excel {tur} gecersiz')
            SONUC.append((False, 'XLSX', tur, 0, 0))
    istek('POST', '/api/export/olmayan', {}, beklenen=(404,))

    # --- eski uclar
    for p in ['/api/stats', '/api/sales', '/api/offers', '/api/renewals', '/api/subscriptions', '/api/notifications/pending',
              '/api/settings', '/api/sync/durum', '/api/sync/gecmis', '/api/kurallar', '/api/siniflandirma',
              '/api/firma-gruplari', '/api/gorunumler', '/api/gorunumler?page=analiz', '/api/check-auth']:
        istek('GET', p)

    # --- yazma uclari
    istek('POST', '/api/kurallar', {'field': 'brand', 'pattern': 'ZZTEST', 'value': 'Test'})
    istek('POST', '/api/kurallar', {'field': 'x', 'pattern': 'a', 'value': 'b'}, beklenen=(400,))
    kurallar = istek('GET', '/api/kurallar')
    for k in kurallar:
        if k['pattern'] == 'ZZTEST':
            istek('DELETE', f"/api/kurallar/{k['id']}")
    istek('POST', '/api/firma-gruplari', {'client_names': [], 'group_name': 'x'}, beklenen=(400,))
    istek('POST', '/api/gorunumler', {'name': 'test görünüm', 'page': 'analiz', 'config': {'rows': ['brand']}})
    for v in istek('GET', '/api/gorunumler'):
        if v['name'] == 'test görünüm':
            istek('DELETE', f"/api/gorunumler/{v['id']}")
    istek('POST', '/api/settings', {'admin_pass_hash': 'x', 'olmayan': 'y', 'smtp_password': ''})
    s = istek('GET', '/api/settings')
    if 'admin_pass_hash' in s or 'olmayan' in s:
        print('  !! ayarlar sizdiriyor / beyaz liste delik')
        SONUC.append((False, 'SET', 'leak', 0, 0))
    istek('POST', '/api/logo/test-connection', {})
    istek('POST', '/api/test-email', {})          # SMTP yok: anlamli hata, 500 degil
    istek('POST', '/api/sales/999999/send-reminder', {}, beklenen=(404,))
    istek('POST', '/api/sales/999999/set-duration', {'duration_months': 12}, beklenen=(404,))
    istek('POST', '/api/sales/1/set-duration', {'duration_months': 'abc'}, beklenen=(400,))
    istek('POST', '/api/sales/abc/renewal', {'karar': 'X'}, beklenen=(400, 404))
    istek('POST', '/api/offers/abc/status', {'status': 'ACCEPTED'}, beklenen=(400, 404))
    istek('GET', '/static/../../database.py', beklenen=(404,))
    istek('GET', '/api/olmayan', beklenen=(404,))
    istek('POST', '/api/olmayan', {}, beklenen=(404,))

    hatali = [r for r in SONUC if not r[0]]
    yavas = sorted(SONUC, key=lambda r: -r[4])[:5]
    print(f'\n{len(SONUC)} istek, {len(hatali)} sorun.')
    print('En yavaşlar:', [(r[2][:40], r[4]) for r in yavas])
    return 1 if hatali else 0


if __name__ == '__main__':
    sys.exit(main())
