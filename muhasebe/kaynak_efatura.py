"""e-Fatura / e-Arsiv (UBL-TR XML) veri kaynagi.

Turkiye'de faturalarin buyuk cogunlugu ayni standart bicimde (UBL-TR) kesilir;
sirket hangi muhasebe programini kullanirsa kullansin satis ve alis satirlari
bu XML'lerde vardir. Bu kaynak bir klasordeki .xml ve .zip dosyalarini okur:

- Sirketin kendisini otomatik bulur: en cok faturada gecen vergi numarasi.
  (Ayarlar'da efatura_vkn girilirse o kullanilir.)
- Satici biz isek SATIS, alici biz isek ALIS; IADE turundeki faturalar ters yonde iade.
- Dovizli faturalar faturadaki kurla TL'ye cevrilir; USD faturalarda kur USD kuru olur.

Logo kaynagiyla ayni arayuzu verir; ambar ve analizler degismeden calisir.
"""

import io
import os
import zipfile
import zlib
from collections import Counter
from xml.etree import ElementTree as ET

import esleme
from kaynak_dosya import YON_KODLARI, kararli_ref

AZAMI_XML = 20 * 1024 * 1024        # tek XML icin ust sinir (bozuk/zararli dosyaya karsi)


def _ad(el):
    return el.tag.rsplit('}', 1)[-1]


def _cocuk(el, *yol):
    """Ad alanindan bagimsiz yol: _cocuk(inv, 'AccountingSupplierParty', 'Party')."""
    for ad in yol:
        if el is None:
            return None
        el = next((c for c in el if _ad(c) == ad), None)
    return el


def _cocuklar(el, ad):
    return [c for c in el if _ad(c) == ad] if el is not None else []


def _metin(el, *yol):
    x = _cocuk(el, *yol) if yol else el
    return (x.text or '').strip() if x is not None and x.text else ''


def _taraf(party):
    """-> {vkn, ad, sehir}"""
    vkn = ''
    for pid in _cocuklar(party, 'PartyIdentification'):
        idel = _cocuk(pid, 'ID')
        if idel is not None and (idel.get('schemeID') or '').upper() in ('VKN', 'TCKN') and idel.text:
            vkn = idel.text.strip()
            break
    ad = _metin(party, 'PartyName', 'Name')
    if not ad:
        kisi = _cocuk(party, 'Person')
        ad = f"{_metin(kisi, 'FirstName')} {_metin(kisi, 'FamilyName')}".strip() if kisi is not None else ''
    return {'vkn': vkn, 'ad': ad or vkn or 'Bilinmeyen', 'sehir': _metin(party, 'PostalAddress', 'CityName')}


def fatura_coz(xml_bayt):
    """Tek UBL faturasi -> dict ya da None (fatura degilse)."""
    if len(xml_bayt) > AZAMI_XML:
        return None
    try:
        kok = ET.fromstring(xml_bayt)
    except ET.ParseError:
        return None
    if _ad(kok) != 'Invoice':
        return None
    para = _metin(kok, 'DocumentCurrencyCode') or 'TRY'
    kur = esleme.sayi(_metin(kok, 'PricingExchangeRate', 'CalculationRate'))
    satirlar = []
    for ln in _cocuklar(kok, 'InvoiceLine'):
        item = _cocuk(ln, 'Item')
        miktar_el = _cocuk(ln, 'InvoicedQuantity')
        satirlar.append({
            'ad': _metin(item, 'Name') or _metin(item, 'Description') or 'Ürün',
            'kod': _metin(item, 'SellersItemIdentification', 'ID') or _metin(item, 'BuyersItemIdentification', 'ID'),
            'marka': _metin(item, 'BrandName'),
            'miktar': esleme.sayi(miktar_el.text if miktar_el is not None else None) or 1.0,
            'tutar': esleme.sayi(_metin(ln, 'LineExtensionAmount')) or 0.0,
        })
    return {
        'no': _metin(kok, 'ID'), 'ettn': _metin(kok, 'UUID'), 'tarih': esleme.tarih(_metin(kok, 'IssueDate')),
        'tur': (_metin(kok, 'InvoiceTypeCode') or 'SATIS').upper(), 'para': para.upper(), 'kur': kur,
        'satici': _taraf(_cocuk(kok, 'AccountingSupplierParty', 'Party')),
        'alici': _taraf(_cocuk(kok, 'AccountingCustomerParty', 'Party')),
        'satirlar': satirlar,
    }


def xml_dosyalari(klasor):
    """Klasordeki .xml ve .zip (ic ice zip dahil) icindeki XML'leri (ad, bayt) olarak verir."""
    def zipten(zf, onek, derinlik=0):
        for bilgi in zf.infolist():
            ad = bilgi.filename.lower()
            if bilgi.file_size > AZAMI_XML * 5:
                continue
            if ad.endswith('.xml'):
                yield f'{onek}/{bilgi.filename}', zf.read(bilgi)
            elif ad.endswith('.zip') and derinlik < 2:
                with zipfile.ZipFile(io.BytesIO(zf.read(bilgi))) as ic:
                    yield from zipten(ic, f'{onek}/{bilgi.filename}', derinlik + 1)

    for kok, _, dosyalar in os.walk(klasor):
        for d in sorted(dosyalar):
            yol = os.path.join(kok, d)
            if d.lower().endswith('.xml'):
                with open(yol, 'rb') as fh:
                    yield d, fh.read()
            elif d.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(yol) as zf:
                        yield from zipten(zf, d)
                except zipfile.BadZipFile:
                    continue


def faturalari_oku(klasor):
    """-> (faturalar, okunamayan_sayisi). Ayni ETTN iki kez gelirse bir kez sayilir."""
    faturalar, gorulen, bozuk = [], set(), 0
    for _, bayt in xml_dosyalari(klasor):
        f = fatura_coz(bayt)
        if not f or not f['tarih']:
            bozuk += 1
            continue
        anahtar = f['ettn'] or f"{f['no']}|{f['satici']['vkn']}"
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        faturalar.append(f)
    return faturalar, bozuk


def sirket_vkn_bul(faturalar):
    """Sirketin kendisi: faturalarin en cogunda (satici ya da alici olarak) gecen vergi no."""
    say = Counter()
    for f in faturalar:
        for t in (f['satici'], f['alici']):
            if t['vkn']:
                say[t['vkn']] += 1
    if not say:
        return None, None
    vkn, adet = say.most_common(1)[0]
    ad = next((t['ad'] for f in faturalar for t in (f['satici'], f['alici']) if t['vkn'] == vkn), vkn)
    return vkn, {'ad': ad, 'oran': adet / len(faturalar)}


def ozet(klasor, vkn=None):
    """Yukleme ekrani icin: kac fatura, sirket kim, tarih araligi, satis/alis sayisi."""
    faturalar, bozuk = faturalari_oku(klasor)
    bulunan, bilgi = sirket_vkn_bul(faturalar)
    vkn = vkn or bulunan
    satis = sum(1 for f in faturalar if f['satici']['vkn'] == vkn)
    tarihler = sorted(f['tarih'] for f in faturalar)
    return {
        'faturalar': len(faturalar), 'okunamayan': bozuk, 'satirlar': sum(len(f['satirlar']) for f in faturalar),
        'sirket_vkn': vkn, 'sirket_ad': (bilgi or {}).get('ad') if vkn == bulunan else None,
        'sirket_orani': round((bilgi or {}).get('oran', 0), 3),
        'satis': satis, 'alis': len(faturalar) - satis,
        'ilk': tarihler[0] if tarihler else None, 'son': tarihler[-1] if tarihler else None,
        'dovizli': sum(1 for f in faturalar if f['para'] != 'TRY'),
    }


class EFaturaKaynagi:
    mod = 'efatura'

    def __init__(self, klasor, vkn=None):
        self.klasor = klasor
        self.vkn = vkn
        self._hazir = False

    def __enter__(self):
        self._coz()
        return self

    def __exit__(self, *a):
        return False

    def markalar(self):
        return dict(self._markalar)

    def urunler(self):
        return self._urunler

    def hizmetler(self):
        return []

    def cariler(self):
        return self._cariler

    def temsilciler(self):
        return []

    def doviz_kurlari(self):
        return dict(self._kurlar)

    def satirlar(self, baslangic=None):
        for s in self._satirlar:
            if not baslangic or s['date'] >= baslangic:
                yield s

    def fatura_sayisi(self):
        return self._fatura_sayisi

    def _coz(self):
        if self._hazir:
            return
        faturalar, self.okunamayan = faturalari_oku(self.klasor)
        vkn = self.vkn or sirket_vkn_bul(faturalar)[0]
        urunler, cariler, markalar, kurlar = {}, {}, {}, {}
        cikti, refs = [], {}
        for f in sorted(faturalar, key=lambda x: (x['tarih'], x['no'])):
            biz_satici = f['satici']['vkn'] == vkn
            karsi = f['alici'] if biz_satici else f['satici']
            iade = f['tur'] == 'IADE'
            # Biz kesmisiz: normalde satis; IADE turundeyse tedarikciye iade (alis iadesi). Bize kesilmis: tersi.
            yon = ('ALIS_IADE' if iade else 'SATIS') if biz_satici else ('SATIS_IADE' if iade else 'ALIS')
            trcode, iocode = YON_KODLARI[yon]
            kur_tl = f['kur'] if f['para'] != 'TRY' and f['kur'] else 1.0
            usd_kur = f['kur'] if f['para'] == 'USD' and f['kur'] else None
            if usd_kur:
                kurlar[f['tarih']] = usd_kur
            ckey = karsi['vkn'] or karsi['ad'].upper()
            if ckey not in cariler:
                cariler[ckey] = {'ref': len(cariler) + 1, 'code': karsi['vkn'], 'name': karsi['ad'], 'cardtype': None,
                                 'email': '', 'phone': '', 'city': karsi['sehir']}
            inv_ref = zlib.crc32((f['ettn'] or f['no']).encode('utf-8')) % 2_000_000_000 or 1
            for s in f['satirlar']:
                ukey = s['kod'] or s['ad'].upper()
                if ukey not in urunler:
                    urunler[ukey] = {'ref': len(urunler) + 1, 'code': s['kod'], 'name': s['ad'], 'grp': '', 'markref': None}
                    if s['marka']:
                        markalar[urunler[ukey]['ref']] = s['marka']
                        urunler[ukey]['markref'] = urunler[ukey]['ref']
                tl = abs(s['tutar']) * kur_tl
                miktar = abs(s['miktar']) or 1.0
                cikti.append({
                    'period': 'K', 'line_ref': kararli_ref(refs, f['no'], ukey), 'inv_ref': inv_ref, 'date': f['tarih'], 'trcode': trcode,
                    'iocode': iocode, 'linetype': 0, 'item_ref': urunler[ukey]['ref'], 'client_ref': cariler[ckey]['ref'],
                    'salesman_ref': 0, 'qty': miktar, 'price': tl / miktar, 'gross': tl, 'net': tl, 'rate': usd_kur,
                    'line_cancelled': 0, 'fiche_no': f['no'], 'inv_cancelled': 0, 'inv_salesman': 0, 'inv_client': 0,
                })
        self._urunler, self._cariler = list(urunler.values()), list(cariler.values())
        self._markalar, self._kurlar, self._satirlar = markalar, kurlar, cikti
        self._fatura_sayisi = len(faturalar)
        self.sirket_vkn = vkn
        self._hazir = True
