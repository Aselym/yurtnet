"""Yapay zekanin sirket verisine erisimi: arka plan profili, salt-okunur araclar, ad maskeleme.

Model Logo'ya ya da veritabanina dogrudan baglanmaz. Senkronla ambara gelen
veriyi iki yoldan gorur:
  1. sirket_profili(): her konusmada verilen ozet (aylik seyir, buyuk musteriler,
     markalar, lisans/abonelik durumu, stok). "Arka plan bilgisi".
  2. araclar: modelin kendi calistirdigi beyaz listeli sorgular (analytics.sorgu,
     lisans/abonelik listeleri, deger arama, stok). Hepsi salt-okunur.

ai_mask_names = ON iken musteri ve temsilci adlari modele "Müşteri #123" olarak
gider; modelin cevabinda ve arac argumanlarinda gercek ada geri cevrilir.
"""
import json
import re
import zlib
from datetime import date, timedelta

import analytics
from database import get_db_connection

AZAMI_SATIR = 40


def _bugun():
    return date.today().isoformat()


def _gun_once(n):
    return (date.today() - timedelta(days=n)).isoformat()


def _yuvarla(v):
    if isinstance(v, float):
        return round(v, 1) if abs(v) < 100 else round(v)
    return v


def _tablo(sonuc, boyut_adlari):
    """analytics.sorgu sonucunu modele uygun kisa satirlara cevirir."""
    out = []
    for r in sonuc['rows'][:AZAMI_SATIR]:
        out.append({**{ad: r.get(f'd{i}') for i, ad in enumerate(boyut_adlari)},
                    **{k[2:]: _yuvarla(v) for k, v in r.items() if k.startswith('m_')}})
    return out


# ------------------------------------------------------------------ maskeleme
class Maske:
    """Gercek ad <-> takma ad. Takma adlar kalici (cari/temsilci numarasina bagli)."""

    def __init__(self, acik):
        self.acik = acik
        self.gercek_takma, self.takma_gercek = {}, {}
        if not acik:
            return
        conn = get_db_connection()
        try:
            for r in conn.execute("SELECT client_ref, name FROM wh_clients WHERE name IS NOT NULL AND name <> ''"):
                self._ekle(r['name'], f"Müşteri #{r['client_ref']}")
            for i, r in enumerate(conn.execute("SELECT DISTINCT group_name FROM client_groups WHERE group_name <> ''"), 1):
                self._ekle(r['group_name'], f"Firma grubu #{i}")
            for r in conn.execute("SELECT salesman_ref, name FROM wh_salesmen WHERE name IS NOT NULL AND name <> ''"):
                self._ekle(r['name'], f"Temsilci #{r['salesman_ref']}")
            for r in conn.execute("SELECT DISTINCT sales_rep FROM sales WHERE sales_rep <> ''"):
                self._ekle(r['sales_rep'], f"Temsilci #{zlib.crc32(r['sales_rep'].encode()) % 9000 + 1000}")
        except Exception:
            pass
        finally:
            conn.close()
        self._ileri = self._desen(self.gercek_takma)
        self._geri = self._desen(self.takma_gercek)

    def _ekle(self, gercek, takma):
        gercek = (gercek or '').strip()
        if len(gercek) < 3 or gercek in self.gercek_takma:
            return
        while takma in self.takma_gercek:
            takma += "'"
        self.gercek_takma[gercek] = takma
        self.takma_gercek[takma] = gercek

    @staticmethod
    def _desen(sozluk):
        if not sozluk:
            return None
        return re.compile('|'.join(re.escape(k) for k in sorted(sozluk, key=len, reverse=True)))

    def gizle(self, metin):
        if not self.acik or not self._ileri or not metin:
            return metin
        return self._ileri.sub(lambda m: self.gercek_takma[m.group(0)], metin)

    def ac(self, metin):
        if not self.acik or not self._geri or not metin:
            return metin
        return self._geri.sub(lambda m: self.takma_gercek[m.group(0)], metin)

    def ac_deger(self, v):
        """Arac argumanindaki takma adi gercege cevirir (liste/dict icinde de)."""
        if isinstance(v, str):
            return self.ac(v)
        if isinstance(v, list):
            return [self.ac_deger(x) for x in v]
        if isinstance(v, dict):
            return {k: self.ac_deger(x) for k, x in v.items()}
        return v


# ------------------------------------------------------------------ arka plan profili
def sirket_profili():
    """Yaklasik 2-3 bin token'lik sirket ozeti (duz metin)."""
    ar = analytics.veri_araligi()
    if not ar.get('lines'):
        return 'Ambarda henüz veri yok (senkron yapılmamış).'
    L = [f"Bugün: {_bugun()}. Ambardaki veri: {ar['first']} – {ar['last']}, {ar['lines']:,} hareket satırı."]
    s = ar.get('last_sync') or {}
    if s.get('finished_at'):
        L.append(f"Son senkron: {s['finished_at']} (kaynak: {s.get('source')}).")
    yil_once, bas24 = _gun_once(365), _gun_once(730)

    def q(**istek):
        return analytics.sorgu(istek)

    ay = q(group_by=['month'], measures=['net_tl', 'profit_tl', 'margin', 'clients'], date_from=bas24, sort={'key': 'd0', 'desc': False})
    L.append('\nAylık net satış (TL), brüt kâr (TL), kâr marjı (%), müşteri sayısı — son 24 ay:')
    L += [f"{r['d0']}: {r['m_net_tl'] or 0:,.0f} | {r['m_profit_tl'] or 0:,.0f} | {(r['m_margin'] or 0):.1f} | {r['m_clients']}" for r in ay['rows']]
    alis = q(group_by=['month'], measures=['net_tl'], direction='ALIS_NET', date_from=yil_once, sort={'key': 'd0', 'desc': False})
    L.append('\nAylık alış (TL) — son 12 ay: ' + ', '.join(f"{r['d0']} {r['m_net_tl'] or 0:,.0f}" for r in alis['rows']))

    for boyut, ad, n in (('client', 'En büyük müşteriler', 15), ('brand', 'Markalar', 10), ('category', 'Kategoriler', 10),
                         ('salesman', 'Temsilciler', 10), ('revenue_type', 'Gelir tipleri', 5)):
        r = q(group_by=[boyut], measures=['net_tl', 'profit_tl', 'margin'], date_from=yil_once, limit=n)
        toplam = r['totals'].get('m_net_tl') or 0
        L.append(f"\n{ad} — son 12 ay (net TL | kâr TL | marj % | pay %):")
        L += [f"{x['d0']}: {x['m_net_tl'] or 0:,.0f} | {x['m_profit_tl'] or 0:,.0f} | {(x['m_margin'] or 0):.1f} | "
              f"{(100 * (x['m_net_tl'] or 0) / toplam if toplam else 0):.1f}" for x in r['rows']]

    conn = get_db_connection()
    try:
        bugun, ufuk = _bugun(), (date.today() + timedelta(days=90)).isoformat()
        yakin = conn.execute("""SELECT client_name, product_name, expiration_date, price FROM sales
                                WHERE status = 'PENDING' AND expiration_date BETWEEN ? AND ? ORDER BY expiration_date LIMIT 15""",
                             (bugun, ufuk)).fetchall()
        sayilar = dict(conn.execute("SELECT status, COUNT(*) FROM sales GROUP BY status").fetchall())
        L.append(f"\nLisanslar: takipte {sayilar.get('PENDING', 0)}, süresi geçmiş {sayilar.get('EXPIRED', 0)}, "
                 f"yenilenmiş {sayilar.get('RENEWED', 0)}, süresi girilmeli {sayilar.get('NEEDS_DURATION', 0)}.")
        if yakin:
            L.append('90 gün içinde dolacak lisanslar (müşteri | ürün | bitiş | satış fiyatı TL):')
            L += [f"{r[0]} | {r[1]} | {r[2]} | {r[3] or 0:,.0f}" for r in yakin]
        abone = conn.execute("""SELECT client_name, product_name, status, days_since_last, avg_interval_days FROM subscriptions
                                WHERE status IN ('AT_RISK','LOST') ORDER BY days_since_last LIMIT 15""").fetchall()
        sayi = dict(conn.execute("SELECT status, COUNT(*) FROM subscriptions GROUP BY status").fetchall())
        L.append(f"\nAbonelikler: aktif {sayi.get('ACTIVE', 0)}, riskli {sayi.get('AT_RISK', 0)}, kayıp {sayi.get('LOST', 0)}.")
        if abone:
            L.append('Riskli/kayıp abonelikler (müşteri | ürün | durum | son faturadan beri gün | normal aralık gün):')
            L += [f"{r[0]} | {r[1]} | {'riskli' if r[2] == 'AT_RISK' else 'kayıp'} | {r[3]} | {r[4]:.0f}" for r in abone]
    finally:
        conn.close()

    try:
        gruplar, toplam = analytics.stok_grup_ozeti(_bugun())
        L.append(f"\nBugünkü stok değeri: {toplam.get('value_tl', 0) or 0:,.0f} TL. Kategoriye göre (TL): " +
                 ', '.join(f"{k} {v['value_tl']:,.0f}" for k, v in sorted(gruplar.items(), key=lambda x: -x[1]['value_tl'])[:8]))
    except Exception:
        pass
    return '\n'.join(L)


# ------------------------------------------------------------------ araclar (salt-okunur)
BOYUT_ADLARI = {k: v[1] for k, v in analytics.BOYUTLAR.items()}
OLCU_ADLARI = {k: v[1] for k, v in analytics.OLCULER.items()}

ARACLAR = [
    {'name': 'analiz_sorgula',
     'description': 'Satış/alış hareketlerinden gruplu analiz. Ciro, kâr, marj, adet, müşteri sayısı vb. '
                    'Boyutlar: ' + ', '.join(f'{k} ({v})' for k, v in BOYUT_ADLARI.items()) +
                    '. Ölçüler: ' + ', '.join(f'{k} ({v})' for k, v in OLCU_ADLARI.items()) + '.',
     'parameters': {'type': 'object', 'properties': {
         'group_by': {'type': 'array', 'items': {'type': 'string', 'enum': list(BOYUT_ADLARI)}, 'maxItems': 2,
                      'description': 'Kırılım boyutları (en fazla 2). Boş = tek toplam.'},
         'measures': {'type': 'array', 'items': {'type': 'string', 'enum': list(OLCU_ADLARI)}, 'description': 'Ölçüler'},
         'date_from': {'type': 'string', 'description': 'YYYY-MM-DD'},
         'date_to': {'type': 'string', 'description': 'YYYY-MM-DD'},
         'direction': {'type': 'string', 'enum': list(analytics.YONLER), 'description': 'SATIS_NET (varsayılan, iadeler düşülmüş satış), ALIS_NET, SATIS, ALIS, TUMU'},
         'filters': {'type': 'object', 'description': 'Boyut -> tam değer listesi. Örn {"brand": ["Dell"]}. '
                     'Müşteri/ürün adını bilmiyorsan önce deger_ara kullan.', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}},
         'limit': {'type': 'integer', 'description': f'En fazla {AZAMI_SATIR}'},
         'sort_desc': {'type': 'boolean', 'description': 'İlk ölçüye göre büyükten küçüğe (varsayılan true; zaman boyutunda false önerilir)'},
     }}},
    {'name': 'deger_ara',
     'description': 'Müşteri, firma grubu ya da ürün adını parça metinle arar; filtre için tam adı bulur.',
     'parameters': {'type': 'object', 'properties': {
         'boyut': {'type': 'string', 'enum': ['client', 'client_group', 'item', 'item_code']},
         'metin': {'type': 'string'}}, 'required': ['boyut', 'metin']}},
    {'name': 'lisanslari_listele',
     'description': 'Süreli lisans takibi (WatchGuard, FortiGate, ESET...). Bitiş tarihi, müşteri, fiyat.',
     'parameters': {'type': 'object', 'properties': {
         'durum': {'type': 'string', 'enum': ['yakinda_dolacak', 'suresi_gecmis', 'yenilenmis', 'sure_girilmeli', 'tumu']},
         'gun': {'type': 'integer', 'description': 'yakinda_dolacak için kaç gün içinde (varsayılan 90)'},
         'musteri': {'type': 'string', 'description': 'Müşteri adında geçen metin (isteğe bağlı)'},
         'limit': {'type': 'integer'}}, 'required': ['durum']}},
    {'name': 'abonelikleri_listele',
     'description': 'Aylık faturalanan abonelikler (Microsoft 365, Azure...) ve faturası kesilmeyi bırakanlar.',
     'parameters': {'type': 'object', 'properties': {
         'durum': {'type': 'string', 'enum': ['ACTIVE', 'AT_RISK', 'LOST', 'tumu']},
         'musteri': {'type': 'string'}, 'limit': {'type': 'integer'}}, 'required': ['durum']}},
    {'name': 'stok_ozeti',
     'description': 'Belirli bir tarihteki stok değeri ve adedi, kategori ya da markaya göre.',
     'parameters': {'type': 'object', 'properties': {
         'tarih': {'type': 'string', 'description': 'YYYY-MM-DD (varsayılan bugün)'},
         'boyut': {'type': 'string', 'enum': ['category', 'brand']}}}},
]

LISANS_DURUM = {'yakinda_dolacak': "status = 'PENDING' AND expiration_date BETWEEN ? AND ?",
                'suresi_gecmis': "status = 'EXPIRED'", 'yenilenmis': "status = 'RENEWED'",
                'sure_girilmeli': "status = 'NEEDS_DURATION'", 'tumu': '1=1'}


def arac_calistir(ad, arg):
    """Modelin istedigi araci calistirir. Doner: JSON metni (hata dahil)."""
    try:
        return json.dumps(_calistir(ad, arg or {}), ensure_ascii=False, default=str)
    except (analytics.GecersizIstek, ValueError, TypeError) as e:
        return json.dumps({'hata': str(e)}, ensure_ascii=False)


def _limit(v, varsayilan=20):
    try:
        return max(1, min(int(v or varsayilan), AZAMI_SATIR))
    except (TypeError, ValueError):
        return varsayilan


def _calistir(ad, a):
    if ad == 'analiz_sorgula':
        gb = list(a.get('group_by') or [])[:2]
        istek = {'group_by': gb, 'measures': a.get('measures') or ['net_tl', 'profit_tl', 'margin'],
                 'date_from': a.get('date_from'), 'date_to': a.get('date_to'),
                 'direction': a.get('direction') or 'SATIS_NET', 'filters': a.get('filters') or {},
                 'limit': _limit(a.get('limit'), 25)}
        zaman = gb and gb[0] in ('day', 'week', 'month', 'quarter', 'year')
        if gb:
            istek['sort'] = {'key': 'd0', 'desc': False} if (zaman and a.get('sort_desc') is not True) else \
                {'key': f"m_{istek['measures'][0]}", 'desc': a.get('sort_desc', True) is not False}
        r = analytics.sorgu(istek)
        return {'satirlar': _tablo(r, [BOYUT_ADLARI[g] for g in gb]),
                'toplam': {k[2:]: _yuvarla(v) for k, v in r['totals'].items()},
                'toplam_satir_sayisi': r['row_count'], 'olcu_adlari': {o: OLCU_ADLARI[o] for o in istek['measures']}}
    if ad == 'deger_ara':
        return analytics.deger_ara(a.get('boyut'), str(a.get('metin') or ''), limit=15)
    if ad == 'lisanslari_listele':
        durum = a.get('durum') or 'yakinda_dolacak'
        if durum not in LISANS_DURUM:
            raise ValueError('Geçersiz durum.')
        where, p = LISANS_DURUM[durum], []
        if durum == 'yakinda_dolacak':
            p += [_bugun(), (date.today() + timedelta(days=int(a.get('gun') or 90))).isoformat()]
        if a.get('musteri'):
            where += ' AND client_name LIKE ?'
            p.append(f"%{a['musteri']}%")
        conn = get_db_connection()
        try:
            rows = conn.execute(f"""SELECT client_name AS musteri, product_name AS urun, sale_date AS satis, expiration_date AS bitis,
                                    status AS durum, price AS fiyat_tl, sales_rep AS temsilci FROM sales WHERE {where}
                                    ORDER BY expiration_date LIMIT ?""", p + [_limit(a.get('limit'))]).fetchall()
            adet = conn.execute(f"SELECT COUNT(*), SUM(price) FROM sales WHERE {where}", p).fetchone()
        finally:
            conn.close()
        return {'lisanslar': [dict(r) for r in rows], 'toplam_adet': adet[0], 'toplam_fiyat_tl': _yuvarla(adet[1] or 0)}
    if ad == 'abonelikleri_listele':
        durum = a.get('durum') or 'AT_RISK'
        where, p = ('1=1', []) if durum == 'tumu' else ('status = ?', [durum])
        if a.get('musteri'):
            where += ' AND client_name LIKE ?'
            p.append(f"%{a['musteri']}%")
        conn = get_db_connection()
        try:
            rows = conn.execute(f"""SELECT client_name AS musteri, product_name AS urun, status AS durum, invoice_count AS fatura_sayisi,
                                    last_invoice_date AS son_fatura, days_since_last AS son_faturadan_beri_gun,
                                    ROUND(avg_interval_days) AS normal_aralik_gun FROM subscriptions WHERE {where}
                                    ORDER BY days_since_last DESC LIMIT ?""", p + [_limit(a.get('limit'))]).fetchall()
        finally:
            conn.close()
        return {'abonelikler': [dict(r) for r in rows]}
    if ad == 'stok_ozeti':
        boyut = a.get('boyut') if a.get('boyut') in ('category', 'brand') else 'category'
        gruplar, toplam = analytics.stok_grup_ozeti(a.get('tarih') or _bugun(), boyut)
        return {'toplam': {k: _yuvarla(v) for k, v in toplam.items()},
                'gruplar': [{boyut: k, **{x: _yuvarla(y) for x, y in v.items()}}
                            for k, v in sorted(gruplar.items(), key=lambda x: -x[1]['value_tl'])[:AZAMI_SATIR]]}
    raise ValueError(f'Bilinmeyen araç: {ad}')
