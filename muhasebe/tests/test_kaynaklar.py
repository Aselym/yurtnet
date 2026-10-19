"""Kaynak bagimsizligi testleri: Excel/CSV ve e-Fatura (UBL-TR) kaynaklari,
otomatik kolon esleme ve bu kaynaklardan ambara uctan uca senkron.

    python -m unittest tests.test_kaynaklar -v
"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
if 'MUHASEBE_DB' not in os.environ:
    os.environ['MUHASEBE_DB'] = os.path.join(tempfile.mkdtemp(), 'test.db')

import database  # noqa: E402
import esleme  # noqa: E402
import kaynaklar  # noqa: E402
import warehouse  # noqa: E402
from kaynak_efatura import EFaturaKaynagi, fatura_coz, ozet  # noqa: E402

BIZ = ('1111111111', 'BİZİM ŞİRKET A.Ş.', 'İSTANBUL')
MUSTERI = ('2222222222', 'ANADOLU GIDA A.Ş.', 'ANKARA')
TEDARIKCI = ('3333333333', 'DAĞITIM LTD. ŞTİ.', 'İZMİR')


def ubl(no, tarih, tur, satici, alici, kalemler, para='TRY', kur=None):
    def taraf(t):
        return (f'<cac:Party><cac:PartyIdentification><cbc:ID schemeID="VKN">{t[0]}</cbc:ID></cac:PartyIdentification>'
                f'<cac:PartyName><cbc:Name>{t[1]}</cbc:Name></cac:PartyName>'
                f'<cac:PostalAddress><cbc:CityName>{t[2]}</cbc:CityName></cac:PostalAddress></cac:Party>')
    satirlar = ''.join(
        f'<cac:InvoiceLine><cbc:ID>{i}</cbc:ID><cbc:InvoicedQuantity unitCode="C62">{q}</cbc:InvoicedQuantity>'
        f'<cbc:LineExtensionAmount currencyID="{para}">{t}</cbc:LineExtensionAmount>'
        f'<cac:Item><cbc:Name>{ad}</cbc:Name><cac:SellersItemIdentification><cbc:ID>{kod}</cbc:ID>'
        f'</cac:SellersItemIdentification></cac:Item></cac:InvoiceLine>' for i, (ad, kod, q, t) in enumerate(kalemler, 1))
    kurx = (f'<cac:PricingExchangeRate><cbc:CalculationRate>{kur}</cbc:CalculationRate></cac:PricingExchangeRate>'
            if kur else '')
    return ('<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2" '
            'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2" '
            'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
            f'<cbc:ID>{no}</cbc:ID><cbc:UUID>{no}-uuid</cbc:UUID><cbc:IssueDate>{tarih}</cbc:IssueDate>'
            f'<cbc:InvoiceTypeCode>{tur}</cbc:InvoiceTypeCode><cbc:DocumentCurrencyCode>{para}</cbc:DocumentCurrencyCode>'
            f'<cac:AccountingSupplierParty>{taraf(satici)}</cac:AccountingSupplierParty>'
            f'<cac:AccountingCustomerParty>{taraf(alici)}</cac:AccountingCustomerParty>{kurx}{satirlar}</Invoice>'
            ).encode('utf-8')


class DegerCozumleme(unittest.TestCase):
    def test_sayi(self):
        self.assertEqual(esleme.sayi('1.234,56'), 1234.56)
        self.assertEqual(esleme.sayi('1,234.56'), 1234.56)
        self.assertEqual(esleme.sayi('₺ 12.500'), 12500.0)
        self.assertEqual(esleme.sayi('99,90 TL'), 99.9)
        self.assertIsNone(esleme.sayi('PRM2025000000119'))     # kod, sayi degil

    def test_tarih(self):
        self.assertEqual(esleme.tarih('19.10.2026'), '2026-10-19')
        self.assertEqual(esleme.tarih('2026-10-19T10:15:00'), '2026-10-19')
        self.assertEqual(esleme.tarih(45000), '2023-03-15')     # Excel seri numarasi
        self.assertIsNone(esleme.tarih('yarın'))

    def test_yon(self):
        self.assertEqual(esleme.yon_coz('Satış Faturası'), 'SATIS')
        self.assertEqual(esleme.yon_coz('Alış Faturası'), 'ALIS')
        self.assertEqual(esleme.yon_coz('Satış İade'), 'SATIS_IADE')
        self.assertEqual(esleme.yon_coz('', -50), 'SATIS_IADE')   # eksi tutar = iade


class OtomatikEsleme(unittest.TestCase):
    def test_daginik_basliklar(self):
        bas = ['Belge Tarihi', 'Evrak No', 'İşlem', 'Müşteri Ünvanı', 'Stok Açıklaması', 'Adet', 'Birim Fiyatı',
               'KDV Hariç Tutar', 'Plasiyer', 'İl', 'Not']
        sat = [['01.10.2026', 'A1', 'Satış Faturası', 'ANADOLU GIDA', 'DELL LATITUDE 5450', 2, '25.000,00', '50.000,00',
                'AYŞE', 'ANKARA', ''],
               ['02.10.2026', 'A2', 'Alış Faturası', 'DAĞITIM LTD', 'DELL LATITUDE 5450', 5, 20000, 100000, '', 'İZMİR', 'x']]
        o, _ = esleme.oner(bas, sat * 10)
        beklenen = {'tarih': 0, 'fatura_no': 1, 'yon': 2, 'cari': 3, 'urun': 4, 'miktar': 5, 'birim_fiyat': 6,
                    'tutar': 7, 'temsilci': 8, 'sehir': 9}
        self.assertEqual({k: v['kolon'] for k, v in o.items()}, beklenen)
        self.assertEqual(esleme.eksikler(o), [])

    def test_adsiz_kolonlarda_tarih_ve_yon_degerden_bulunur(self):
        bas = ['K1', 'K2', 'Müşteri', 'Ürün', 'Tutar']
        sat = [['2026-10-0' + str(i % 9 + 1), 'Satış' if i % 2 else 'Alış', 'X A.Ş.', 'ÜRÜN', 100] for i in range(20)]
        o, _ = esleme.oner(bas, sat)
        self.assertEqual(o['tarih']['kolon'], 0)
        self.assertEqual(o['yon']['kolon'], 1)


class EFatura(unittest.TestCase):
    def setUp(self):
        self.klasor = tempfile.mkdtemp()
        dosyalar = {
            's1.xml': ubl('SAT1', '2026-01-10', 'SATIS', BIZ, MUSTERI, [('DELL LATITUDE 5450', 'D1', 2, 60000)]),
            'a1.xml': ubl('ALS1', '2026-01-05', 'SATIS', TEDARIKCI, BIZ, [('DELL LATITUDE 5450', 'D1', 5, 1000)],
                          para='USD', kur=40),
            'i1.xml': ubl('IAD1', '2026-01-20', 'IADE', MUSTERI, BIZ, [('DELL LATITUDE 5450', 'D1', 1, 30000)]),
        }
        for ad, b in dosyalar.items():
            open(os.path.join(self.klasor, ad), 'wb').write(b)

    def test_coz_ve_sirketi_bul(self):
        f = fatura_coz(open(os.path.join(self.klasor, 's1.xml'), 'rb').read())
        self.assertEqual((f['no'], f['tarih'], f['satici']['vkn']), ('SAT1', '2026-01-10', BIZ[0]))
        oz = ozet(self.klasor)
        self.assertEqual((oz['faturalar'], oz['sirket_vkn'], oz['satis'], oz['alis']), (3, BIZ[0], 1, 2))

    def test_yon_ve_doviz(self):
        with EFaturaKaynagi(self.klasor) as k:
            sat = {s['fiche_no']: s for s in k.satirlar()}
        self.assertEqual(warehouse.yon_bul(sat['SAT1']['trcode'], True), 'SATIS')
        self.assertEqual(warehouse.yon_bul(sat['ALS1']['trcode'], True), 'ALIS')
        self.assertEqual(warehouse.yon_bul(sat['IAD1']['trcode'], True), 'SATIS_IADE')
        self.assertAlmostEqual(sat['ALS1']['net'], 40000)        # 1000 USD x 40
        self.assertEqual(sat['ALS1']['rate'], 40)

    def test_satir_kimligi_kararli(self):
        # ayni fatura satiri her okumada ayni kimligi almali (lisanslar cogalmasin)
        with EFaturaKaynagi(self.klasor) as k1:
            r1 = sorted(s['line_ref'] for s in k1.satirlar())
        with EFaturaKaynagi(self.klasor) as k2:
            r2 = sorted(s['line_ref'] for s in k2.satirlar())
        self.assertEqual(r1, r2)
        self.assertEqual(len(set(r1)), len(r1))


class UctanUcaSenkron(unittest.TestCase):
    """Dosya ve e-Fatura kaynagindan ambara: satirlar, yon ve FIFO kar."""

    def setUp(self):
        if os.path.exists(database.DB_PATH):
            os.remove(database.DB_PATH)
        database.init_db()
        self.tmp = tempfile.mkdtemp()

    def _ayar(self, **ek):
        a = database.get_settings()
        a.update({'data_start_date': ''}, **ek)
        return a

    def test_csv_kaynagi(self):
        klasor = os.path.join(self.tmp, 'tablo')
        os.makedirs(klasor)
        open(os.path.join(klasor, 'r.csv'), 'w', encoding='utf-8').write(
            'Tarih;Fiş No;İşlem;Cari;Ürün;Miktar;Tutar\n'
            '05.01.2026;A1;Alış Faturası;DAĞITIM;DELL 5450;5;100.000,00\n'
            '10.01.2026;S1;Satış Faturası;ANADOLU;DELL 5450;2;60.000,00\n')
        e = {'dosya': 'r.csv', 'esleme': {'tarih': 0, 'fatura_no': 1, 'yon': 2, 'cari': 3, 'urun': 4, 'miktar': 5, 'tutar': 6}}
        with mock.patch.object(kaynaklar, 'DOSYA_KLASORU', klasor):
            oz = warehouse.senkronize_et(self._ayar(logo_source='dosya', dosya_esleme=json.dumps(e)))
        self.assertEqual((oz['source'], oz['lines']), ('dosya', 2))
        c = database.get_db_connection()
        s = c.execute("SELECT direction, net_tl, cost_tl FROM wh_lines WHERE fiche_no='S1'").fetchone()
        self.assertEqual(s['direction'], 'SATIS')
        self.assertAlmostEqual(s['cost_tl'], 40000)              # 2 adet x 20.000 (FIFO)
        c.close()

    def test_efatura_kaynagi(self):
        klasor = os.path.join(self.tmp, 'efatura')
        os.makedirs(klasor)
        open(os.path.join(klasor, 's.xml'), 'wb').write(
            ubl('SAT1', '2026-01-10', 'SATIS', BIZ, MUSTERI, [('DELL 5450', 'D1', 2, 60000)]))
        open(os.path.join(klasor, 'a.xml'), 'wb').write(
            ubl('ALS1', '2026-01-05', 'SATIS', TEDARIKCI, BIZ, [('DELL 5450', 'D1', 5, 100000)]))
        open(os.path.join(klasor, 'b.xml'), 'wb').write(
            ubl('ALS2', '2026-01-06', 'SATIS', TEDARIKCI, BIZ, [('KABLO', 'K1', 10, 500)]))
        with mock.patch.object(kaynaklar, 'EFATURA_KLASORU', klasor):
            oz = warehouse.senkronize_et(self._ayar(logo_source='efatura'))
        self.assertEqual(oz['lines'], 3)
        c = database.get_db_connection()
        s = c.execute("SELECT direction, cost_tl FROM wh_lines WHERE fiche_no='SAT1'").fetchone()
        self.assertEqual(s['direction'], 'SATIS')
        self.assertAlmostEqual(s['cost_tl'], 40000)
        c.close()


if __name__ == '__main__':
    unittest.main()
