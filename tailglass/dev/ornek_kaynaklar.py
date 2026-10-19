"""Demo ambarindan deneme kaynaklari uretir (Excel/CSV ve e-Fatura eslemesini test etmek icin).

    python dev/ornek_kaynaklar.py        # -> dev/ornek_veri/satis_raporu.xlsx, efatura_arsivi.zip

- satis_raporu.xlsx: gercek hayattaki gibi daginik bir rapor. Ustte baslik
  satirlari, Turkce kolon adlari, bazi tutarlar "1.234,56" metni.
- efatura_arsivi.zip: UBL-TR biciminde satis ve alis faturalari (bazilari USD).
"""

import io
import os
import random
import sqlite3
import sys
import zipfile
import zlib
from collections import defaultdict
from xml.sax.saxutils import escape

BURASI = os.path.dirname(os.path.abspath(__file__))
CIKTI = os.path.join(BURASI, 'ornek_veri')
SIRKET = {'vkn': '1234567890', 'ad': 'Örnek Bilişim Teknolojileri A.Ş.', 'sehir': 'İSTANBUL'}


def veri(baslangic='2025-10-01'):
    c = sqlite3.connect(os.path.join(BURASI, 'demo_app.db'))
    c.row_factory = sqlite3.Row
    return c.execute('''
        SELECT l.date, l.fiche_no, l.direction, l.qty, l.net_tl, l.rate, i.name AS urun, i.code AS kod,
               i.brand AS marka, i.category AS kategori, c.name AS cari, c.code AS cari_kodu, c.city AS sehir,
               s.name AS temsilci, l.client_ref
        FROM wh_lines l JOIN wh_items i ON i.item_ref = l.item_ref
        LEFT JOIN wh_clients c ON c.client_ref = l.client_ref
        LEFT JOIN wh_salesmen s ON s.salesman_ref = l.salesman_ref
        WHERE l.cancelled = 0 AND l.direction IN ('SATIS', 'ALIS', 'SATIS_IADE') AND l.date >= ?
        ORDER BY l.date, l.fiche_no''', (baslangic,)).fetchall()


def tr_sayi(x):
    return f'{x:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def excel_uret(satirlar):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapor'
    ws.append(['Örnek Ticaret A.Ş. — Satış ve alış hareketleri'])
    ws.append(['Rapor tarihi: 19.10.2026'])
    ws.append([])
    ws.append(['Fatura Tarihi', 'Belge No', 'İşlem', 'Müşteri Ünvanı', 'Cari Kodu', 'Stok Kodu', 'Stok Açıklaması',
               'Miktar', 'Birim Fiyat', 'Tutar (KDV Hariç)', 'Plasiyer', 'İl', 'Not'])
    rnd = random.Random(7)
    islem = {'SATIS': 'Satış Faturası', 'ALIS': 'Alış Faturası', 'SATIS_IADE': 'Satış İade'}
    for r in satirlar:
        tutar = round(r['net_tl'], 2)
        bf = round(tutar / r['qty'], 2) if r['qty'] else tutar
        ws.append([
            # tarihlerin bir kismi metin (gg.aa.yyyy), bir kismi gercek tarih
            r['date'] if rnd.random() < 0.5 else '.'.join(reversed(r['date'].split('-'))),
            r['fiche_no'], islem[r['direction']], r['cari'], r['cari_kodu'], r['kod'], r['urun'],
            r['qty'], bf, tr_sayi(tutar) if rnd.random() < 0.3 else tutar, r['temsilci'] or '', r['sehir'] or '', ''])
    yol = os.path.join(CIKTI, 'satis_raporu.xlsx')
    wb.save(yol)
    return yol


def _taraf(vkn, ad, sehir):
    return (f'<cac:Party><cac:PartyIdentification><cbc:ID schemeID="VKN">{vkn}</cbc:ID></cac:PartyIdentification>'
            f'<cac:PartyName><cbc:Name>{escape(ad)}</cbc:Name></cac:PartyName>'
            f'<cac:PostalAddress><cbc:CityName>{escape(sehir or "")}</cbc:CityName></cac:PostalAddress></cac:Party>')


def ubl(no, tarih, tur, satici, alici, satirlar, para='TRY', kur=None):
    bolum = ''.join(
        f'<cac:InvoiceLine><cbc:ID>{i}</cbc:ID><cbc:InvoicedQuantity unitCode="C62">{s["qty"]:g}</cbc:InvoicedQuantity>'
        f'<cbc:LineExtensionAmount currencyID="{para}">{s["tutar"]:.2f}</cbc:LineExtensionAmount>'
        f'<cac:Item><cbc:Name>{escape(s["urun"])}</cbc:Name>'
        + (f'<cbc:BrandName>{escape(s["marka"])}</cbc:BrandName>' if s.get('marka') else '')
        + f'<cac:SellersItemIdentification><cbc:ID>{escape(s["kod"] or "")}</cbc:ID></cac:SellersItemIdentification></cac:Item>'
        f'<cac:Price><cbc:PriceAmount currencyID="{para}">{s["tutar"] / (s["qty"] or 1):.2f}</cbc:PriceAmount></cac:Price>'
        f'</cac:InvoiceLine>' for i, s in enumerate(satirlar, 1))
    kur_xml = (f'<cac:PricingExchangeRate><cbc:SourceCurrencyCode>{para}</cbc:SourceCurrencyCode>'
               f'<cbc:TargetCurrencyCode>TRY</cbc:TargetCurrencyCode><cbc:CalculationRate>{kur:.4f}</cbc:CalculationRate>'
               f'</cac:PricingExchangeRate>') if para != 'TRY' else ''
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
            'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
            'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
            f'<cbc:UBLVersionID>2.1</cbc:UBLVersionID><cbc:CustomizationID>TR1.2</cbc:CustomizationID>'
            f'<cbc:ProfileID>TICARIFATURA</cbc:ProfileID><cbc:ID>{no}</cbc:ID>'
            f'<cbc:UUID>{no}-0000-4000-8000-000000000000</cbc:UUID><cbc:IssueDate>{tarih}</cbc:IssueDate>'
            f'<cbc:InvoiceTypeCode>{tur}</cbc:InvoiceTypeCode><cbc:DocumentCurrencyCode>{para}</cbc:DocumentCurrencyCode>'
            f'<cac:AccountingSupplierParty>{_taraf(*satici)}</cac:AccountingSupplierParty>'
            f'<cac:AccountingCustomerParty>{_taraf(*alici)}</cac:AccountingCustomerParty>'
            f'{kur_xml}{bolum}</Invoice>').encode('utf-8')


def efatura_uret(satirlar):
    rnd = random.Random(11)
    faturalar = defaultdict(list)
    for r in satirlar:
        faturalar[(r['fiche_no'], r['date'], r['direction'], r['cari'], r['cari_kodu'], r['sehir'])].append(r)
    biz = (SIRKET['vkn'], SIRKET['ad'], SIRKET['sehir'])
    yol = os.path.join(CIKTI, 'efatura_arsivi.zip')
    with zipfile.ZipFile(yol, 'w', zipfile.ZIP_DEFLATED) as zf:
        for (no, tarih, yon, cari, ckod, sehir), kalemler in faturalar.items():
            karsi = (f'{zlib.crc32((ckod or cari or "x").encode()) % 10**10:010d}', cari or 'Bilinmeyen', sehir or '')
            usd = rnd.random() < 0.15 and kalemler[0]['rate']
            kur = kalemler[0]['rate'] if usd else None
            sat = [{'qty': k['qty'], 'tutar': (k['net_tl'] / kur) if usd else k['net_tl'], 'urun': k['urun'],
                    'kod': k['kod'], 'marka': k['marka'] if rnd.random() < 0.5 else ''} for k in kalemler]
            if yon == 'SATIS':
                x = ubl(no, tarih, 'SATIS', biz, karsi, sat, 'USD' if usd else 'TRY', kur)
            elif yon == 'SATIS_IADE':      # musteri bize iade faturasi keser
                x = ubl(no, tarih, 'IADE', karsi, biz, sat)
            else:                           # alis: tedarikci bize keser
                x = ubl(no, tarih, 'SATIS', karsi, biz, sat, 'USD' if usd else 'TRY', kur)
            klasor = 'giden' if yon == 'SATIS' else 'gelen'
            zf.writestr(f'{klasor}/{tarih[:7]}/{no}.xml', x)
    return yol, len(faturalar)


if __name__ == '__main__':
    os.makedirs(CIKTI, exist_ok=True)
    s = veri(sys.argv[1] if len(sys.argv) > 1 else '2025-10-01')
    print('satir:', len(s))
    print('excel:', excel_uret(s))
    print('e-fatura:', *efatura_uret(s))
