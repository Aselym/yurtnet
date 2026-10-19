"""Excel'e aktarma: ekranda ne goruluyorsa (ayni filtre ve kirilimlarla) o.

Her dosyanin ilk sayfasi "Rapor bilgisi": hangi donem, hangi filtreler,
ne zaman uretildi — Excel baskasina iletildiginde baglam kaybolmasin.
"""

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import analytics

# Kurus/sent gosterilmez (kullanici istegi: kafa karistiriyor). Sayilar tam;
# yalnizca USD kuru gibi gercekten ondalikli degerler ondalikli yazilir.
BICIM = {'tl': '#,##0 "₺"', 'usd': '"$"#,##0', 'num': '#,##0', 'pct': '0.0"%"', 'date': '@', 'text': '@'}


def _bicim(tip, v):
    if tip == 'num' and isinstance(v, float) and not v.is_integer() and abs(v) < 1000:
        return '#,##0.00'
    return BICIM.get(tip, 'General')
BASLIK_DOLGU = PatternFill('solid', fgColor='1F2933')
BASLIK_YAZI = Font(bold=True, color='FFFFFF')
TOPLAM_YAZI = Font(bold=True)
INCE = Side(style='thin', color='D9DDE3')


def _sayfa_yaz(ws, kolonlar, satirlar, toplam=None, baslik=None):
    r0 = 1
    if baslik:
        ws.cell(row=1, column=1, value=baslik).font = Font(bold=True, size=13)
        r0 = 3
    for j, k in enumerate(kolonlar, 1):
        c = ws.cell(row=r0, column=j, value=k['label'])
        c.fill, c.font = BASLIK_DOLGU, BASLIK_YAZI
        c.alignment = Alignment(vertical='center', wrap_text=True)
    for i, satir in enumerate(satirlar, r0 + 1):
        for j, k in enumerate(kolonlar, 1):
            v = satir.get(k['key'])
            c = ws.cell(row=i, column=j, value=v)
            if k.get('type') in BICIM and isinstance(v, (int, float)):
                c.number_format = _bicim(k['type'], v)
    if toplam:
        i = r0 + len(satirlar) + 1
        ws.cell(row=i, column=1, value='TOPLAM').font = TOPLAM_YAZI
        for j, k in enumerate(kolonlar, 1):
            if j == 1:
                continue
            v = toplam.get(k['key'])
            if isinstance(v, (int, float)):
                c = ws.cell(row=i, column=j, value=v)
                c.font = TOPLAM_YAZI
                c.number_format = BICIM.get(k.get('type'), 'General')
                c.border = Border(top=INCE)
    for j, k in enumerate(kolonlar, 1):
        uzunluk = max([len(str(k['label']))] + [len(f"{s.get(k['key'])}") for s in satirlar[:300]])
        ws.column_dimensions[get_column_letter(j)].width = min(max(10, uzunluk + 2), 60)
    ws.freeze_panes = ws.cell(row=r0 + 1, column=1)
    ws.auto_filter.ref = f"A{r0}:{get_column_letter(len(kolonlar))}{r0 + len(satirlar)}"


def _bilgi_sayfasi(wb, istek, baslik):
    ws = wb.active
    ws.title = 'Rapor bilgisi'
    satirlar = [
        ('Rapor', baslik),
        ('Üretildi', datetime.now().strftime('%d.%m.%Y %H:%M')),
        ('Dönem', f"{istek.get('date_from') or 'başlangıç'} — {istek.get('date_to') or 'bugün'}"),
    ]
    if istek.get('direction'):
        yonler = {d['key']: d['label'] for d in analytics.meta()['directions']}
        satirlar.append(('Hareket', yonler.get(istek['direction'], istek['direction'])))
    for boyut, degerler in (istek.get('filters') or {}).items():
        if degerler:
            etiket = analytics.BOYUTLAR.get(boyut, (None, boyut))[1]
            if isinstance(degerler, dict):
                onek = 'HARİÇ: ' if degerler.get('not') else ''
                degerler = degerler.get('values') or []
            else:
                onek = ''
            satirlar.append((f'Filtre — {etiket}', onek + ', '.join(map(str, degerler))))
    if istek.get('search'):
        satirlar.append(('Arama', istek['search']))
    if istek.get('group_by'):
        gb = istek['group_by'] if isinstance(istek['group_by'], list) else [istek['group_by']]
        satirlar.append(('Kırılım', ' › '.join(analytics.BOYUTLAR.get(g, (None, g))[1] for g in gb)))
    satirlar.append(('Not', 'Maliyet ve kâr FIFO yöntemiyle tahmin edilmiştir; USD tutarlar işlem günündeki kurla '
                            'hesaplanmıştır.'))
    for i, (k, v) in enumerate(satirlar, 1):
        ws.cell(row=i, column=1, value=k).font = TOPLAM_YAZI
        ws.cell(row=i, column=2, value=v)
    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 90


def _kaydet(wb):
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def sorgu_excel(istek, baslik='Analiz'):
    sonuc = analytics.sorgu({**istek, 'limit': 0})
    wb = Workbook()
    _bilgi_sayfasi(wb, istek, baslik)
    ws = wb.create_sheet('Veri')
    toplam = {k: v for k, v in sonuc['totals'].items()}
    if sonuc.get('pivot'):
        toplam = None
    _sayfa_yaz(ws, sonuc['columns'], sonuc['rows'], toplam)
    return _kaydet(wb)


def satirlar_excel(istek, baslik='Hareket listesi'):
    # Excel tarafinda tum satirlar: 5000'lik sayfalarla
    tum, offset = [], 0
    kolonlar = None
    while True:
        s = analytics.satirlar({**istek, 'limit': 5000, 'offset': offset})
        kolonlar = s['columns']
        tum += s['rows']
        offset += 5000
        if offset >= s['total'] or offset >= 200000:
            break
    secili = istek.get('columns')
    if secili:
        kolonlar = [k for k in kolonlar if k['key'] in secili]
    wb = Workbook()
    _bilgi_sayfasi(wb, istek, baslik)
    ws = wb.create_sheet('Satırlar')
    toplam = {k['key']: sum((r.get(k['key']) or 0) for r in tum) for k in kolonlar
              if k['type'] in ('tl', 'usd') or k['key'] == 'qty'}
    _sayfa_yaz(ws, kolonlar, tum, toplam)
    return _kaydet(wb)


def stok_excel(istek):
    s = analytics.stok({**istek, 'limit': 0})
    kolonlar = [
        {'key': 'item', 'label': 'Ürün', 'type': 'text'}, {'key': 'item_code', 'label': 'Kod', 'type': 'text'},
        {'key': 'brand', 'label': 'Marka', 'type': 'text'}, {'key': 'category', 'label': 'Kategori', 'type': 'text'},
        {'key': 'qty', 'label': 'Eldeki adet', 'type': 'num'},
        {'key': 'unit_cost_tl', 'label': 'Son alış birim (TL)', 'type': 'tl'},
        {'key': 'value_tl', 'label': 'Değer (TL)', 'type': 'tl'}, {'key': 'value_usd', 'label': 'Değer (USD)', 'type': 'usd'},
        {'key': 'last_purchase', 'label': 'Son alış', 'type': 'date'}, {'key': 'last_sale', 'label': 'Son satış', 'type': 'date'},
        {'key': 'days_since_move', 'label': 'Hareketsiz (gün)', 'type': 'num'},
        {'key': 'sold_recent', 'label': f"Son {s['velocity_days']} gün satış", 'type': 'num'},
        {'key': 'cover_days', 'label': 'Kaç gün yeter', 'type': 'num'},
    ]
    wb = Workbook()
    _bilgi_sayfasi(wb, {**istek, 'date_to': s['as_of'], 'date_from': None}, f"Stok durumu — {s['as_of']}")
    ws = wb.create_sheet('Stok')
    _sayfa_yaz(ws, kolonlar, s['rows'], {'qty': s['totals']['qty'], 'value_tl': s['totals']['value_tl'],
                                          'value_usd': s['totals']['value_usd']})
    return _kaydet(wb)


def donem_excel(istek):
    d = analytics.donem_raporu(istek)
    wb = Workbook()
    _bilgi_sayfasi(wb, {**istek, 'date_from': d['date_from'], 'date_to': d['date_to'], 'group_by': [d['group_by']]},
                   'Dönem raporu')
    ws = wb.create_sheet('Özet')
    t = d['totals']
    ozet = [
        ('Dönem başı stok değeri (TL)', t['open_value_tl'], 'tl'), ('Alışlar (TL)', t['buy_tl'], 'tl'),
        ('Alışlar (USD)', t['buy_usd'], 'usd'), ('Alış faturası', t['buy_invoices'], 'num'),
        ('Satışlar (TL)', t['sell_tl'], 'tl'), ('Satışlar (USD)', t['sell_usd'], 'usd'),
        ('Satış faturası', t['sell_invoices'], 'num'), ('Müşteri sayısı', t['clients'], 'num'),
        ('Brüt kâr (TL, FIFO)', t['profit_tl'], 'tl'), ('Kâr marjı', t['margin'], 'pct'),
        ('Dönem sonu stok değeri (TL)', t['close_value_tl'], 'tl'),
        ('Dönem sonu stok değeri (USD)', t['close_value_usd'], 'usd'),
    ]
    for i, (k, v, tip) in enumerate(ozet, 1):
        ws.cell(row=i, column=1, value=k).font = TOPLAM_YAZI
        c = ws.cell(row=i, column=2, value=v)
        c.number_format = BICIM[tip]
    ws.column_dimensions['A'].width = 34
    ws.column_dimensions['B'].width = 22

    kolonlar = [
        {'key': 'group', 'label': d['group_label'], 'type': 'text'},
        {'key': 'open_qty', 'label': 'Dönem başı adet', 'type': 'num'},
        {'key': 'open_value_tl', 'label': 'Dönem başı değer (TL)', 'type': 'tl'},
        {'key': 'buy_qty', 'label': 'Alınan adet', 'type': 'num'}, {'key': 'buy_tl', 'label': 'Alış (TL)', 'type': 'tl'},
        {'key': 'buy_usd', 'label': 'Alış (USD)', 'type': 'usd'},
        {'key': 'sell_qty', 'label': 'Satılan adet', 'type': 'num'}, {'key': 'sell_tl', 'label': 'Satış (TL)', 'type': 'tl'},
        {'key': 'sell_usd', 'label': 'Satış (USD)', 'type': 'usd'},
        {'key': 'profit_tl', 'label': 'Brüt kâr (TL)', 'type': 'tl'}, {'key': 'margin', 'label': 'Marj', 'type': 'pct'},
        {'key': 'close_qty', 'label': 'Dönem sonu adet', 'type': 'num'},
        {'key': 'close_value_tl', 'label': 'Dönem sonu değer (TL)', 'type': 'tl'},
    ]
    ws2 = wb.create_sheet(d['group_label'][:30])
    _sayfa_yaz(ws2, kolonlar, d['rows'], {k['key']: sum((r.get(k['key']) or 0) for r in d['rows'])
                                         for k in kolonlar if k['type'] in ('tl', 'usd', 'num')})
    for ad, anahtar in (('En çok satılan müşteriler', 'top_customers'), ('En çok alınan tedarikçiler', 'top_suppliers'),
                        ('En çok satılan ürünler', 'top_items_sold'), ('En çok alınan ürünler', 'top_items_bought')):
        w = wb.create_sheet(ad[:30])
        _sayfa_yaz(w, [{'key': 'd0', 'label': 'Ad', 'type': 'text'},
                       {'key': 'm_net_tl', 'label': 'Tutar (TL)', 'type': 'tl'},
                       {'key': 'm_net_usd', 'label': 'Tutar (USD)', 'type': 'usd'}], d[anahtar])
    return _kaydet(wb)
