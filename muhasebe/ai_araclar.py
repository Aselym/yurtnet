"""Yapay zeka asistaninin kullanabilecegi araclar (function calling).

Model veritabanina dogrudan erismez; yalnizca bu beyaz listeli araclari cagirir:
  veri_sorgula      analiz motoru (analytics.sorgu) — toplu sonuc, en fazla 50 satir
  deger_ara         musteri / urun adinin tam yazimini bulur (filtre icin)
  tahmin            gelecek aylar icin istatistiksel ongoru; rakamlari PROGRAM hesaplar
  lisans_bitisleri  yaklasan lisans bitisleri
  abonelikleri_listele, stok_ozeti
Hepsi salt okunur. Musteri e-posta/telefonu hicbir aracta donmez.
"""
import json
from datetime import date, timedelta

import analytics
from database import get_db_connection

AZAMI_SATIR = 25
TAHMIN_OLCULERI = ('net_tl', 'net_usd', 'qty', 'profit_tl', 'profit_usd', 'invoices')
_FILTRE_ACIKLAMA = ('Boyut -> değer listesi. Örn {"brand": ["WatchGuard"], "client": ["ABC LTD"]}. '
                    'Müşteri/ürün adını bilmiyorsan önce deger_ara ile tam yazımını bul.')

ARACLAR = [
    {
        'ad': 'veri_sorgula',
        'aciklama': ('Şirketin satış/alış veritabanından toplu analiz sorgusu. Kırılıma (group_by) göre ölçüleri '
                     'toplar. Rakam gereken her soruda önce bunu kullan.'),
        'parametreler': {
            'type': 'object',
            'properties': {
                'group_by': {'type': 'array', 'items': {'type': 'string', 'enum': list(analytics.BOYUTLAR)},
                             'description': 'Kırılımlar (en fazla 2). Boş = tek toplam.'},
                'measures': {'type': 'array', 'items': {'type': 'string', 'enum': list(analytics.OLCULER)},
                             'description': 'Ölçüler. net_tl=satış tutarı, profit_tl=brüt kâr, margin=kâr marjı %, qty=adet.'},
                'date_from': {'type': 'string', 'description': 'YYYY-MM-DD (dahil)'},
                'date_to': {'type': 'string', 'description': 'YYYY-MM-DD (dahil)'},
                'filters': {'type': 'object', 'description': _FILTRE_ACIKLAMA},
                'direction': {'type': 'string', 'enum': list(analytics.YONLER),
                              'description': 'SATIS_NET (varsayılan, iadeler düşülmüş satış) ya da ALIS_NET (alışlar).'},
                'limit': {'type': 'integer', 'description': f'En fazla {AZAMI_SATIR}. Büyükten küçüğe sıralı.'},
            },
            'required': ['measures'],
        },
    },
    {
        'ad': 'deger_ara',
        'aciklama': 'Müşteri, firma grubu ya da ürün adının veritabanındaki tam yazımını arar.',
        'parametreler': {
            'type': 'object',
            'properties': {
                'boyut': {'type': 'string', 'enum': ['client', 'client_group', 'item', 'item_code']},
                'metin': {'type': 'string', 'description': 'Adın bir parçası'},
            },
            'required': ['boyut', 'metin'],
        },
    },
    {
        'ad': 'tahmin',
        'aciklama': ('Gelecek aylar için istatistiksel öngörü (mevsimsellik + büyüme ya da trend). Rakamları program '
                     'hesaplar; geçmişte bu yöntemin ortalama hata yüzdesini de verir. Gelecek hakkında rakam '
                     'söyleyeceksen MUTLAKA bunu kullan, kendin tahmin hesaplama.'),
        'parametreler': {
            'type': 'object',
            'properties': {
                'measure': {'type': 'string', 'enum': list(TAHMIN_OLCULERI)},
                'ay_sayisi': {'type': 'integer', 'description': 'Kaç ay ileri (1-12)'},
                'filters': {'type': 'object', 'description': _FILTRE_ACIKLAMA},
                'direction': {'type': 'string', 'enum': ['SATIS_NET', 'ALIS_NET']},
            },
            'required': ['measure'],
        },
    },
    {
        'ad': 'lisans_bitisleri',
        'aciklama': 'Önümüzdeki N gün içinde süresi dolacak lisanslar (yenileme fırsatları) ve tahmini yenileme tutarı.',
        'parametreler': {
            'type': 'object',
            'properties': {'gun': {'type': 'integer', 'description': 'Kaç gün içinde (varsayılan 90)'}},
        },
    },
    {
        'ad': 'abonelikleri_listele',
        'aciklama': 'Aylık faturalanan abonelikler (Microsoft 365, Azure...); faturası kesilmeyi bırakan riskli/kayıp müşteriler.',
        'parametreler': {
            'type': 'object',
            'properties': {
                'durum': {'type': 'string', 'enum': ['ACTIVE', 'AT_RISK', 'LOST', 'tumu'],
                          'description': 'ACTIVE=düzenli, AT_RISK=gecikmiş, LOST=kayıp'},
                'musteri': {'type': 'string', 'description': 'Müşteri adında geçen metin (isteğe bağlı)'},
            },
            'required': ['durum'],
        },
    },
    {
        'ad': 'stok_ozeti',
        'aciklama': 'Belirli bir tarihteki stok değeri ve adedi (kategori ya da markaya göre), ölü stok dahil.',
        'parametreler': {
            'type': 'object',
            'properties': {
                'tarih': {'type': 'string', 'description': 'YYYY-MM-DD (varsayılan bugün)'},
                'boyut': {'type': 'string', 'enum': ['category', 'brand']},
            },
        },
    },
]


def sistem_bilgisi():
    """Sistem metnine eklenen kisa veri ozeti: modelin hangi tarihleri sorabilecegini bilmesi icin."""
    a = analytics.veri_araligi()
    return (f"Bugün: {date.today().isoformat()}. Veritabanında {a.get('first') or '?'} ile {a.get('last') or '?'} "
            f"arasında {a.get('lines') or 0} fatura satırı var.")


def _yuvarla(v):
    if isinstance(v, float):
        return round(v) if abs(v) >= 100 else round(v, 2)
    return v


def _filtreler(f):
    if not isinstance(f, dict):
        return {}
    return {k: [str(x) for x in (v if isinstance(v, list) else [v])][:30] for k, v in f.items()
            if k in analytics.BOYUTLAR}


def veri_sorgula(group_by=None, measures=None, date_from=None, date_to=None, filters=None, direction=None, limit=None):
    gb = [g for g in (group_by or []) if g in analytics.BOYUTLAR][:2]
    istek = {'group_by': gb, 'measures': [m for m in (measures or ['net_tl']) if m in analytics.OLCULER][:4] or ['net_tl'],
             'date_from': date_from, 'date_to': date_to, 'filters': _filtreler(filters),
             'direction': direction or 'SATIS_NET', 'limit': max(1, min(int(limit or 20), AZAMI_SATIR))}
    if gb and gb[0] in ('day', 'week', 'month', 'quarter', 'year'):
        istek['sort'] = {'key': 'd0', 'desc': False}
    r = analytics.sorgu(istek)
    adlar = {c['key']: c['label'] for c in r['columns']}
    satirlar = [{adlar.get(k, k): _yuvarla(v) for k, v in s.items()} for s in r['rows']]
    return {'kolonlar': [c['label'] for c in r['columns']], 'satirlar': satirlar,
            'toplam': {adlar.get(k, k): _yuvarla(v) for k, v in (r['totals'] or {}).items()},
            'toplam_satir_sayisi': r['row_count'], 'gosterilen': len(satirlar),
            'para_birimi': 'TL tutarlar Türk lirası, USD tutarlar dolar'}


def deger_ara(boyut, metin):
    return {'sonuclar': [x['v'] for x in analytics.deger_ara(boyut, str(metin)[:60], 15)]}


# ------------------------------------------------------------------ tahmin
def _ay_ekle(ay, n):
    y, m = map(int, ay.split('-'))
    m += n
    return f'{y + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}'


def _ongor(gecmis, k):
    """gecmis: tam aylarin degerleri (eskiden yeniye). k adim ileri tahmin listesi."""
    n = len(gecmis)
    if n >= 24:
        son12, onceki12 = sum(gecmis[-12:]), sum(gecmis[-24:-12])
        buyume = min(max(son12 / onceki12, 0.5), 2.0) if onceki12 > 0 else 1.0
        return [gecmis[n - 12 + (i % 12)] * buyume ** (1 + i // 12) for i in range(k)], 'mevsimsel'
    y = gecmis[-12:]
    m = len(y)
    mx, my = (m - 1) / 2, sum(y) / m
    payda = sum((i - mx) ** 2 for i in range(m)) or 1
    egim = sum((i - mx) * (v - my) for i, v in enumerate(y)) / payda
    return [max(my + egim * (m - 1 - mx + 1 + i), 0) for i in range(k)], 'trend'


def tahmin(measure='net_tl', ay_sayisi=6, filters=None, direction=None):
    if measure not in TAHMIN_OLCULERI:
        measure = 'net_tl'
    k = max(1, min(int(ay_sayisi or 6), 12))
    bu_ay = date.today().strftime('%Y-%m')
    r = analytics.sorgu({'group_by': ['month'], 'measures': [measure], 'filters': _filtreler(filters),
                         'direction': direction or 'SATIS_NET', 'date_to': (date.today().replace(day=1) - timedelta(days=1)).isoformat()})
    veri = {s['d0']: s[f'm_{measure}'] or 0 for s in r['rows'] if s.get('d0')}
    if not veri:
        return {'hata': 'Bu seçim için geçmiş veri yok.'}
    # bosluksuz aylik seri: ilk aydan gecen aya kadar (satis olmayan ay = 0)
    aylar, ay = [], min(veri)
    while ay < bu_ay:
        aylar.append(ay)
        ay = _ay_ekle(ay, 1)
    seri = [float(veri.get(a, 0)) for a in aylar]
    if len(seri) < 6:
        return {'hata': f'Tahmin için en az 6 tam ay gerekli; {len(seri)} ay var.'}

    # geriye donuk sinama: son 6 ayi, her biri icin yalnizca onceki aylari bilerek tahmin et
    hatalar = []
    for i in range(max(6, len(seri) - 6), len(seri)):
        p = _ongor(seri[:i], 1)[0][0]
        if seri[i]:
            hatalar.append(abs(p - seri[i]) / abs(seri[i]))
    hata = sum(hatalar) / len(hatalar) if hatalar else None

    degerler, yontem = _ongor(seri, k)
    tahminler = []
    for i, v in enumerate(degerler):
        t = {'ay': _ay_ekle(aylar[-1], i + 1), 'tahmin': _yuvarla(v)}
        if hata is not None:
            t['alt'], t['ust'] = _yuvarla(v * max(1 - hata, 0)), _yuvarla(v * (1 + hata))
        tahminler.append(t)
    return {
        'olcu': analytics.OLCULER[measure][1],
        'yontem': ('Mevsimsel: geçen yılın aynı ayı × son 12 ayın bir önceki 12 aya göre büyümesi' if yontem == 'mevsimsel'
                   else 'Trend: son 12 ayın doğrusal eğilimi (24 aydan az veri olduğu için mevsimsellik yok)'),
        'gecmis_son_12_ay': [{'ay': a, 'deger': _yuvarla(v)} for a, v in zip(aylar[-12:], seri[-12:])],
        'tahmin': tahminler,
        'gecmiste_ortalama_hata_yuzde': round(hata * 100, 1) if hata is not None else None,
        'not': 'İstatistiksel öngörüdür; büyük tek seferlik satışlar, kur ve fiyat değişimleri hesaba katılmaz. İçinde bulunulan ay tamamlanmadığı için dahil edilmedi.',
    }


def lisans_bitisleri(gun=90):
    gun = max(1, min(int(gun or 90), 730))
    bugun = date.today()
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT client_name, product_name, expiration_date, price FROM sales "
            "WHERE status NOT IN ('EXPIRED','NEEDS_DURATION','RENEWED') AND expiration_date BETWEEN ? AND ? "
            "ORDER BY expiration_date LIMIT 60", (bugun.isoformat(), (bugun + timedelta(days=gun)).isoformat())).fetchall()
    finally:
        conn.close()
    liste = [{'musteri': r['client_name'], 'urun': r['product_name'], 'bitis': r['expiration_date'],
              'son_satis_tutari_tl': _yuvarla(r['price']) if r['price'] else None} for r in rows]
    return {'gun': gun, 'adet': len(liste), 'lisanslar': liste,
            'toplam_son_satis_tutari_tl': _yuvarla(sum(x['son_satis_tutari_tl'] or 0 for x in liste))}


def abonelikleri_listele(durum='AT_RISK', musteri=None):
    where, p = ('1=1', []) if durum == 'tumu' else ('status = ?', [durum if durum in ('ACTIVE', 'AT_RISK', 'LOST') else 'AT_RISK'])
    if musteri:
        where += ' AND client_name LIKE ?'
        p.append(f'%{str(musteri)[:60]}%')
    conn = get_db_connection()
    try:
        rows = conn.execute(f"""SELECT client_name, product_name, status, invoice_count, last_invoice_date, days_since_last,
                                avg_interval_days FROM subscriptions WHERE {where} ORDER BY days_since_last DESC LIMIT ?""",
                            p + [AZAMI_SATIR]).fetchall()
    finally:
        conn.close()
    ad = {'ACTIVE': 'düzenli', 'AT_RISK': 'riskli', 'LOST': 'kayıp'}
    return {'abonelikler': [{'musteri': r['client_name'], 'urun': r['product_name'], 'durum': ad.get(r['status'], r['status']),
                             'fatura_sayisi': r['invoice_count'], 'son_fatura': r['last_invoice_date'],
                             'son_faturadan_beri_gun': r['days_since_last'],
                             'normal_aralik_gun': _yuvarla(r['avg_interval_days'])} for r in rows]}


def stok_ozeti(tarih=None, boyut='category'):
    boyut = boyut if boyut in ('category', 'brand') else 'category'
    gruplar, toplam = analytics.stok_grup_ozeti(tarih or date.today().isoformat(), boyut)
    return {'toplam': {k: _yuvarla(v) for k, v in toplam.items()},
            'gruplar': [{boyut: k, **{x: _yuvarla(y) for x, y in v.items()}}
                        for k, v in sorted(gruplar.items(), key=lambda x: -x[1]['value_tl'])[:AZAMI_SATIR]]}


CALISTIR = {'veri_sorgula': veri_sorgula, 'deger_ara': deger_ara, 'tahmin': tahmin, 'lisans_bitisleri': lisans_bitisleri,
            'abonelikleri_listele': abonelikleri_listele, 'stok_ozeti': stok_ozeti}


def calistir(ad, argumanlar):
    """Arac cagrisini guvenle calistirir; sonuc her zaman JSON metni (hata dahil)."""
    if ad not in CALISTIR:
        return json.dumps({'hata': f'Bilinmeyen araç: {ad}'}, ensure_ascii=False)
    if isinstance(argumanlar, str):
        try:
            argumanlar = json.loads(argumanlar or '{}')
        except ValueError:
            argumanlar = {}
    if not isinstance(argumanlar, dict):
        argumanlar = {}
    izinli = ARACLAR[[a['ad'] for a in ARACLAR].index(ad)]['parametreler'].get('properties', {})
    try:
        sonuc = CALISTIR[ad](**{k: v for k, v in argumanlar.items() if k in izinli})
    except (ValueError, TypeError) as e:
        sonuc = {'hata': f'Geçersiz istek: {e}'}
    return json.dumps(sonuc, ensure_ascii=False, default=str)[:6000]
