"""Otomatik kolon esleme: bilinmeyen bir tabloyu (Excel/CSV) Tailglass'in
ortak is modeline (fatura satiri) cevirir.

Yapay zeka gerekmez: kolon adlari (Turkce/Ingilizce es anlamlilar), veri tipi
(tarih, sayi, metin), deger dagilimi (kac farkli deger, buyukluk, satis/alis
kelimeleri) birlikte puanlanir. Her oneri bir guven puani ve gerekce tasir;
kullanici ekranda onaylar ya da duzeltir. Veri hicbir yere gonderilmez.
"""

import re
import unicodedata
from datetime import date, datetime, timedelta

# alan anahtari -> (etiket, tip, zorunlu, es anlamlilar)
ALANLAR = {
    'tarih':       ('Tarih', 'tarih', True, ['tarih', 'fatura tarihi', 'fis tarihi', 'belge tarihi', 'islem tarihi',
                                            'date', 'invoice date', 'issue date', 'duzenleme tarihi']),
    'fatura_no':   ('Fatura / fiş no', 'metin', False, ['fatura no', 'fatura numarasi', 'fis no', 'belge no', 'evrak no',
                                                       'invoice no', 'invoice number', 'document no', 'ettn', 'seri sira']),
    'yon':         ('İşlem türü (satış / alış)', 'metin', False, ['islem turu', 'fatura turu', 'tur', 'tip', 'yon',
                                                                 'hareket', 'type', 'direction', 'fis turu', 'belge turu']),
    'cari':        ('Müşteri / tedarikçi', 'metin', True, ['cari', 'cari adi', 'cari unvan', 'unvan', 'musteri', 'musteri adi',
                                                          'firma', 'firma adi', 'alici', 'tedarikci', 'customer',
                                                          'client', 'account', 'company', 'satici', 'karsi taraf']),
    'cari_kodu':   ('Cari kodu', 'metin', False, ['cari kodu', 'cari kod', 'musteri kodu', 'hesap kodu', 'vkn', 'vergi no',
                                                 'tckn', 'customer code', 'account code', 'vergi numarasi']),
    'urun':        ('Ürün / hizmet adı', 'metin', True, ['urun', 'urun adi', 'stok adi', 'malzeme', 'malzeme adi', 'mal adi',
                                                       'hizmet', 'aciklama', 'kalem', 'item', 'product', 'description',
                                                       'urun hizmet', 'mal hizmet', 'stok aciklamasi']),
    'urun_kodu':   ('Ürün kodu', 'metin', False, ['urun kodu', 'stok kodu', 'malzeme kodu', 'kod', 'sku', 'item code',
                                                 'product code', 'barkod', 'part number', 'parca no']),
    'miktar':      ('Miktar', 'sayi', False, ['miktar', 'adet', 'qty', 'quantity', 'amount qty', 'birim miktar']),
    'birim_fiyat': ('Birim fiyat', 'sayi', False, ['birim fiyat', 'fiyat', 'unit price', 'price', 'satis fiyati',
                                                 'birim fiyati']),
    'tutar':       ('Tutar (KDV hariç, TL)', 'sayi', True, ['tutar', 'toplam', 'net tutar', 'satir tutari', 'mal hizmet tutari',
                                                          'kdv haric tutar', 'matrah', 'total', 'amount', 'net amount',
                                                          'line total', 'ciro', 'tl tutar', 'tutar tl']),
    'tutar_usd':   ('Tutar (USD)', 'sayi', False, ['usd', 'tutar usd', 'dolar', 'usd tutar', 'amount usd']),
    'kur':         ('Döviz kuru (USD)', 'sayi', False, ['kur', 'doviz kuru', 'usd kuru', 'exchange rate', 'rate']),
    'temsilci':    ('Satış temsilcisi', 'metin', False, ['temsilci', 'satis temsilcisi', 'satici personel', 'plasiyer',
                                                       'sales rep', 'salesman', 'sorumlu']),
    'sehir':       ('Şehir', 'metin', False, ['sehir', 'il', 'city', 'bolge']),
    'marka':       ('Marka', 'metin', False, ['marka', 'brand', 'uretici', 'manufacturer']),
    'kategori':    ('Ürün grubu', 'metin', False, ['kategori', 'grup', 'urun grubu', 'stok grubu', 'category', 'group']),
}
ALAN_SIRASI = list(ALANLAR)

_TR = str.maketrans('çğıöşüÇĞİÖŞÜ', 'cgiosuCGIOSU')


def norm(metin):
    """'Fatura Tarihi ' -> 'fatura tarihi' (Turkce karakterler sadelesir)."""
    t = str(metin or '').translate(_TR)
    t = unicodedata.normalize('NFKD', t).encode('ascii', 'ignore').decode()
    t = re.sub(r'[^a-zA-Z0-9]+', ' ', t).strip().lower()
    return t


# ------------------------------------------------------------------ deger cozumleme
def sayi(v):
    """'1.234,56' / '1,234.56' / 1234.56 / '₺ 1.234' -> float; cozulemezse None."""
    if v is None or v == '':
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    ham = re.sub(r'(?i)\b(try|tl|usd|eur)\b|[₺$€\s]', '', str(v).strip())
    if re.search(r'[^\d,.\-+]', ham):
        return None                      # harf iceren deger (PRM2025... gibi kod) sayi degil
    t = ham.replace('+', '')
    if not t or t in ('-', '.', ','):
        return None
    if ',' in t and '.' in t:
        # son gelen ayirac ondalik
        if t.rfind(',') > t.rfind('.'):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif ',' in t:
        # 1,5 ya da 1,234 (binlik)? 3 haneli tek grup + baska ayirac yoksa binlik say
        parcalar = t.split(',')
        t = t.replace(',', '') if len(parcalar) > 2 or (len(parcalar[-1]) == 3 and len(parcalar[0]) <= 3 and parcalar[0] not in ('0', '-0')) \
            else t.replace(',', '.')
    elif t.count('.') > 1:
        t = t.replace('.', '')
    elif '.' in t:
        tam, ond = t.split('.')
        if len(ond) == 3 and tam not in ('0', '-0', ''):
            t = tam + ond          # 1.234 -> binlik (Turkce yazim)
    try:
        return float(t)
    except ValueError:
        return None


_TARIH_BICIM = ['%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%y', '%Y-%m-%dT%H:%M:%S',
                '%d.%m.%Y %H:%M:%S', '%d.%m.%Y %H:%M', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y']


def tarih(v):
    """Excel tarihi, 'gg.aa.yyyy', 'yyyy-aa-gg' ... -> 'yyyy-aa-gg'; cozulemezse None."""
    if v is None or v == '':
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (int, float)) and 20000 < v < 80000:      # Excel seri numarasi
        return (date(1899, 12, 30) + timedelta(days=int(v))).isoformat()
    t = str(v).strip()
    for b in _TARIH_BICIM:
        try:
            d = datetime.strptime(t[:19] if 'T' in t or ':' in t else t, b).date()
            if 1990 <= d.year <= 2100:
                return d.isoformat()
        except ValueError:
            continue
    return None


SATIS_KELIME = ('satis', 'sales', 'sale', 'giden', 'cikis', 'satilan', 'musteri', 'sat ')
ALIS_KELIME = ('alis', 'alim', 'purchase', 'gelen', 'giris', 'satin', 'tedarik')
IADE_KELIME = ('iade', 'return', 'refund')


def yon_coz(v, tutar=None, varsayilan='SATIS'):
    """Islem turu metni (+ negatif tutar) -> SATIS | ALIS | SATIS_IADE | ALIS_IADE."""
    t = f' {norm(v)} '
    iade = any(k in t for k in IADE_KELIME)
    if any(k in t for k in ALIS_KELIME):
        temel = 'ALIS'
    elif any(k in t for k in SATIS_KELIME):
        temel = 'SATIS'
    else:
        temel = varsayilan
    if tutar is not None and tutar < 0:
        iade = True
    return f'{temel}_IADE' if iade else temel


# ------------------------------------------------------------------ profil + esleme
def kolon_profili(ad, degerler):
    dolu = [v for v in degerler if v not in (None, '')]
    n = len(dolu) or 1
    sayilar = [sayi(v) for v in dolu]
    sayisal = [x for x in sayilar if x is not None]
    tarihler = [tarih(v) for v in dolu]
    yonlu = sum(1 for v in dolu if any(k in f' {norm(v)} ' for k in SATIS_KELIME + ALIS_KELIME + IADE_KELIME))
    return {
        'ad': str(ad), 'norm': norm(ad), 'dolu': len(dolu) / max(len(degerler), 1),
        'tarih_orani': sum(1 for x in tarihler if x) / n,
        'sayi_orani': len(sayisal) / n,
        'tamsayi_orani': (sum(1 for x in sayisal if float(x).is_integer()) / len(sayisal)) if sayisal else 0,
        'medyan': sorted(sayisal)[len(sayisal) // 2] if sayisal else None,
        'farkli_orani': len({str(v) for v in dolu}) / n,
        'ort_uzunluk': sum(len(str(v)) for v in dolu) / n,
        'yon_orani': yonlu / n,
        'ornek': [str(v)[:40] for v in dolu[:4]],
    }


def _ad_puani(p, alan):
    es = ALANLAR[alan][3]
    if p['norm'] in es:
        return 1.0, f'kolon adı "{p["ad"]}"'
    for e in es:
        if e and (f' {e} ' in f' {p["norm"]} ' or (len(p['norm']) > 3 and f' {p["norm"]} ' in f' {e} ')):
            return 0.8, f'kolon adında "{e}" geçiyor'
    return 0.0, ''


def _tip_puani(p, alan):
    """Degerlerin alana uygunlugu (0-1) ve gerekce."""
    tip = ALANLAR[alan][1]
    if tip == 'tarih':
        return p['tarih_orani'], f'değerlerin %{round(p["tarih_orani"] * 100)}\'i tarih'
    if tip == 'sayi':
        s = p['sayi_orani'] * (0.4 if p['tarih_orani'] > 0.8 else 1)
        if alan == 'miktar':
            s *= 0.5 + 0.5 * p['tamsayi_orani'] * (1 if (p['medyan'] or 0) < 1000 else 0.4)
        if alan in ('tutar', 'birim_fiyat'):
            s *= 1 if (p['medyan'] or 0) >= 1 else 0.6
        if alan == 'kur':
            s *= 1 if 0.5 < (p['medyan'] or 0) < 200 and p['tamsayi_orani'] < 0.5 else 0.2
        return s, f'değerlerin %{round(p["sayi_orani"] * 100)}\'i sayı'
    # metin
    s = (1 - p['sayi_orani']) * (1 - p['tarih_orani'])
    if alan == 'yon':
        s = p['yon_orani']
        return s, f'değerlerin %{round(s * 100)}\'inde satış/alış/iade geçiyor'
    if alan in ('urun', 'cari'):
        s *= min(1.0, p['ort_uzunluk'] / 8)
    return s, 'metin değerler'


def oner(kolonlar, satirlar):
    """kolonlar: baslik listesi, satirlar: [[...], ...] -> {alan: {kolon, guven, neden}}.

    Her kolon en fazla bir alana atanir; en yuksek puanli eslesmeler once.
    """
    profiller = [kolon_profili(k, [r[i] if i < len(r) else None for r in satirlar]) for i, k in enumerate(kolonlar)]
    adaylar = []
    for i, p in enumerate(profiller):
        if p['dolu'] < 0.05:
            continue
        for alan in ALAN_SIRASI:
            ad_p, ad_neden = _ad_puani(p, alan)
            tip_p, tip_neden = _tip_puani(p, alan)
            if ad_p == 0 and alan not in ('tarih', 'yon'):
                # adsiz eslesme yalnizca cok belirgin tipte (tarih kolonu, satis/alis kolonu)
                continue
            puan = ad_p * 0.65 + tip_p * 0.35 if ad_p else tip_p * 0.7
            if puan >= 0.45:
                neden = ', '.join(x for x in (ad_neden, tip_neden) if x)
                adaylar.append((puan, i, alan, neden))
    adaylar.sort(reverse=True)
    sonuc, kullanilan = {}, set()
    for puan, i, alan, neden in adaylar:
        if alan in sonuc or i in kullanilan:
            continue
        sonuc[alan] = {'kolon': i, 'guven': round(min(puan, 1.0), 2), 'neden': neden}
        kullanilan.add(i)
    return sonuc, profiller


def eksikler(esleme):
    """Zorunlu ama eslenmemis alanlar. Tutar yoksa miktar x birim fiyat yeterli."""
    eksik = []
    for alan, (etiket, _, zorunlu, _) in ALANLAR.items():
        if not zorunlu or alan in esleme:
            continue
        if alan == 'tutar' and 'birim_fiyat' in esleme:
            continue
        eksik.append(etiket)
    return eksik
