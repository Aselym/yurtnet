"""Cekirdek is mantigi testleri: FIFO, siniflandirma, analiz motoru, hatirlatma asamalari.

Her test gecici, bos bir veritabaninda calisir (MUHASEBE_DB); canli veriye
dokunmaz.

    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
_tmp = tempfile.mkdtemp()
os.environ['MUHASEBE_DB'] = os.path.join(_tmp, 'test.db')

import database  # noqa: E402
import siniflandirma as s  # noqa: E402


def satir(conn, ref, item, tarih, yon, qty, net, iocode=None, client=1, cancelled=0, usd_kur=10.0):
    io = iocode or (1 if yon in ('ALIS', 'SATIS_IADE') else 4)
    tr = {'ALIS': 1, 'SATIS': 8, 'SATIS_IADE': 3, 'ALIS_IADE': 6}.get(yon, 0)
    conn.execute('''INSERT INTO wh_lines (line_ref, period, inv_ref, fiche_no, date, trcode, iocode, linetype, direction,
                    client_ref, item_ref, salesman_ref, qty, price_tl, gross_tl, net_tl, rate, net_usd, cancelled)
                    VALUES (?, '01', ?, ?, ?, ?, ?, 0, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)''',
                 (ref, ref, f'F{ref}', tarih, tr, io, yon, client, item, qty, net / qty, net, net, usd_kur, net / usd_kur, cancelled))


class Taban(unittest.TestCase):
    def setUp(self):
        if os.path.exists(database.DB_PATH):
            os.remove(database.DB_PATH)
        database.init_db()
        self.conn = database.get_db_connection()
        self.conn.execute("INSERT INTO wh_items (item_ref, code, name, brand, category, kind, revenue_type) "
                          "VALUES (1, 'D1', 'DELL LATITUDE 5450', 'Dell', 'Dizüstü Bilgisayar', 'urun', 'Ürün')")
        self.conn.execute("INSERT INTO wh_items (item_ref, code, name, brand, category, kind, revenue_type) "
                          "VALUES (2, 'W1', 'WATCHGUARD T45 1YIL', 'WatchGuard', 'Lisans', 'lisans', 'Tekrarlayan')")
        self.conn.execute("INSERT INTO wh_clients VALUES (1, 'C1', 'ANADOLU GIDA A.S.', 1, '', '', 'ISTANBUL')")
        self.conn.execute("INSERT INTO wh_clients VALUES (2, 'C2', 'EGE TEKSTIL LTD.STI.', 1, '', '', 'IZMIR')")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()


class FifoTesti(Taban):
    def test_iki_lottan_karsilanan_satis(self):
        import warehouse
        satir(self.conn, 1, 1, '2024-01-01', 'ALIS', 10, 1000)   # 100/adet
        satir(self.conn, 2, 1, '2024-02-01', 'ALIS', 5, 600)     # 120/adet
        satir(self.conn, 3, 1, '2024-03-01', 'SATIS', 12, 2400)
        satir(self.conn, 4, 1, '2024-04-01', 'SATIS', 5, 1000)   # 3 adet kaldi -> eksik
        self.conn.commit()
        warehouse.fifo_hesapla(self.conn)
        r3 = self.conn.execute('SELECT * FROM wh_lines WHERE line_ref = 3').fetchone()
        self.assertAlmostEqual(r3['cost_tl'], 10 * 100 + 2 * 120)
        self.assertEqual(r3['cost_date'], '2024-01-01')       # ilk karsilanan lotun tarihi
        self.assertEqual(r3['cost_complete'], 1)
        r4 = self.conn.execute('SELECT * FROM wh_lines WHERE line_ref = 4').fetchone()
        self.assertAlmostEqual(r4['cost_tl'], 3 * 120)
        self.assertEqual(r4['cost_complete'], 0)              # stok yetmedi: kar hesabina girmez

    def test_iptal_satir_fifo_disinda(self):
        import warehouse
        satir(self.conn, 1, 1, '2024-01-01', 'ALIS', 1, 100)
        satir(self.conn, 2, 1, '2024-01-02', 'SATIS', 1, 150, cancelled=1)
        satir(self.conn, 3, 1, '2024-01-03', 'SATIS', 1, 160)
        self.conn.commit()
        warehouse.fifo_hesapla(self.conn)
        r3 = self.conn.execute('SELECT * FROM wh_lines WHERE line_ref = 3').fetchone()
        self.assertEqual(r3['cost_complete'], 1, 'iptal satis lotu tuketmemeli')


class AnalizTesti(Taban):
    def setUp(self):
        super().setUp()
        satir(self.conn, 1, 1, '2025-01-05', 'ALIS', 10, 1000)
        satir(self.conn, 2, 1, '2025-01-10', 'SATIS', 4, 800, client=1)
        satir(self.conn, 3, 1, '2025-02-10', 'SATIS', 2, 400, client=2)
        satir(self.conn, 4, 2, '2025-02-11', 'ALIS', 1, 50)
        satir(self.conn, 5, 2, '2025-02-12', 'SATIS', 1, 90, client=1)
        satir(self.conn, 6, 1, '2025-02-20', 'SATIS_IADE', 1, 200, client=2)
        self.conn.commit()
        import warehouse
        warehouse.fifo_hesapla(self.conn)

    def test_iade_dusulur(self):
        import analytics
        net = analytics.sorgu({'direction': 'SATIS_NET', 'measures': ['net_tl', 'qty']})['totals']
        self.assertAlmostEqual(net['m_net_tl'], 800 + 400 + 90 - 200)
        brut = analytics.sorgu({'direction': 'SATIS', 'measures': ['net_tl']})['totals']
        self.assertAlmostEqual(brut['m_net_tl'], 1290)

    def test_kirilim_ve_filtre(self):
        import analytics
        r = analytics.sorgu({'direction': 'SATIS_NET', 'group_by': ['revenue_type'], 'measures': ['net_tl']})
        d = {x['d0']: x['m_net_tl'] for x in r['rows']}
        self.assertAlmostEqual(d['Tekrarlayan'], 90)
        r = analytics.sorgu({'direction': 'SATIS', 'filters': {'city': {'not': True, 'values': ['ISTANBUL']}},
                             'measures': ['net_tl']})
        self.assertAlmostEqual(r['totals']['m_net_tl'], 400)

    def test_pivot(self):
        import analytics
        r = analytics.sorgu({'direction': 'SATIS', 'group_by': ['brand'], 'pivot_by': 'month', 'measures': ['qty']})
        dell = next(x for x in r['rows'] if x['d0'] == 'Dell')
        self.assertEqual(dell['p::2025-01'], 4)
        self.assertEqual(dell['p::2025-02'], 2)
        self.assertEqual(dell['_total'], 6)

    def test_zaman_pivotu_sinirda_eskiler_basa(self):
        import analytics
        r = analytics.sorgu({'direction': 'SATIS', 'group_by': ['brand'], 'pivot_by': 'day',
                             'measures': ['qty'], 'pivot_limit': 2})
        # 3 satis gunu, 2 kolon sinir: en eski gunler 'Daha eski' olarak basta, en yeni gun sonda
        self.assertEqual(r['pivot']['values'], ['Daha eski', '2025-02-12'])
        dell = next(x for x in r['rows'] if x['d0'] == 'Dell')
        self.assertEqual(dell['p::Daha eski'], 6)

    def test_beyaz_liste_disi_reddedilir(self):
        import analytics
        with self.assertRaises(analytics.GecersizIstek):
            analytics.sorgu({'group_by': ["brand; DROP TABLE sales --"]})
        with self.assertRaises(analytics.GecersizIstek):
            analytics.sorgu({'measures': ['SUM(1)']})
        with self.assertRaises(analytics.GecersizIstek):
            analytics.sorgu({'filters': {'1=1 OR': ['x']}})

    def test_filtre_degeri_parametre(self):
        import analytics
        r = analytics.sorgu({'direction': 'SATIS', 'filters': {'brand': ["' OR 1=1 --"]}, 'measures': ['net_tl']})
        self.assertIsNone(r['totals']['m_net_tl'])

    def test_artik_yil_karsilastirma(self):
        import analytics
        self.assertEqual(analytics._gecen_yil('2024-02-29'), '2023-02-28')
        g = analytics.genel_bakis({'date_from': '2024-02-29', 'date_to': '2024-02-29', 'compare': 'year'})
        self.assertEqual(g['compare_from'], '2023-02-28')

    def test_stok_tarihte(self):
        import analytics
        s1 = analytics.stok({'as_of': '2025-01-31'})
        self.assertEqual({r['item']: r['qty'] for r in s1['rows']}['DELL LATITUDE 5450'], 6)
        s2 = analytics.stok({'as_of': '2025-03-01'})
        self.assertEqual({r['item']: r['qty'] for r in s2['rows']}['DELL LATITUDE 5450'], 5)  # 10-4-2+1


class SiniflandirmaTesti(unittest.TestCase):
    def test_lisans_beyaz_listesi(self):
        self.assertEqual(s.tur_bul('WATCHGUARD WGT45413 T45 3 YIL BASIC SECURITY'), 'lisans')
        self.assertEqual(s.tur_bul('DELL LATITUDE 3450 I5 3YIL GARANTI'), 'urun')      # garanti suresi lisans degil
        self.assertEqual(s.tur_bul('WATCHGUARD T45 APPLIANCE ONLY'), 'urun')          # donanim
        self.assertEqual(s.tur_bul('MICROSOFT 365 BUSINESS STANDART'), 'abonelik')
        self.assertEqual(s.tur_bul('MICROSOFT WINDOWS 11 PRO OEM'), 'kalici')

    def test_sure(self):
        self.assertEqual(s.sure_ay_bul('FORTIGATE 60F 1 YIL'), 12)
        self.assertEqual(s.sure_ay_bul('GUVLIC3Y'), 36)
        self.assertIsNone(s.sure_ay_bul('WATCHGUARD WGT1850203'))                     # model kodu yil degil
        self.assertEqual(s.sure_ay_bul('FORTIGATE 12 AY BUNDLE'), 12)

    def test_oncelik_kural_logo_sozluk(self):
        u = {'name': 'TP-LINK ARCHER C6', 'code': 'X', 'logo_brand': 'Tp-Link', 'logo_group': 'AG'}
        r = s.siniflandir(u, [], {})
        self.assertEqual((r['brand'], r['brand_src']), ('TP-Link', 'logo'))           # yazim farki birlesir
        self.assertEqual(r['category'], 'Ağ Ürünleri')                                 # grup kodu esleme
        kural = [{'field': 'brand', 'pattern': 'ARCHER', 'value': 'Archer'}]
        self.assertEqual(s.siniflandir(u, kural, {})['brand_src'], 'kural')

    def test_genel_kelime_marka_sayilmaz(self):
        u = {'name': 'HDMI KABLO 3MT', 'code': '', 'logo_brand': '', 'logo_group': ''}
        r = s.siniflandir(u, [], {'HDMI': 50})
        self.assertEqual(r['brand'], 'Markasız')
        self.assertEqual(r['category'], 'Kablo / Bağlantı')


class HatirlatmaTesti(unittest.TestCase):
    def setUp(self):
        if os.path.exists(database.DB_PATH):
            os.remove(database.DB_PATH)
        database.init_db()

    def _lisans(self, gun_kala, gonderilen=0):
        bitis = (date.today() + timedelta(days=gun_kala)).isoformat()
        c = database.get_db_connection()
        c.execute('''INSERT INTO sales (product_name, client_name, client_email, sale_date, duration_type,
                     duration_months, expiration_date, reminder_type, status, reminders_sent_count)
                     VALUES ('ESET 1 YIL', 'X A.S.', '', '2025-01-01', '1_YEAR', 12, ?, 'STAGED', 'PENDING', ?)''',
                  (bitis, gonderilen))
        c.commit()
        c.close()

    def test_asama_secimi(self):
        import scheduler
        self._lisans(4)                      # 10,5,1 -> ikinci asama (5 gun)
        self._lisans(4, gonderilen=2)        # zaten gonderilmis
        self._lisans(30)                     # henuz erken
        gonderilen = []
        with mock.patch.object(scheduler, 'send_reminder_email', lambda s, a: (gonderilen.append(a), (True, 'ok'))[1]), \
             mock.patch.object(scheduler, 'send_windows_toast', lambda *a: None):
            n = scheduler.check_and_send_reminders()
        self.assertEqual(n, 1)
        self.assertEqual(gonderilen, ['SECOND_REMINDER'])

    def test_ayarlanabilir_gunler(self):
        import scheduler
        c = database.get_db_connection()
        c.execute("UPDATE settings SET value = '30,14' WHERE key = 'reminder_days'")
        c.commit()
        c.close()
        self._lisans(20)
        gonderilen = []
        with mock.patch.object(scheduler, 'send_reminder_email', lambda s, a: (gonderilen.append(a), (True, 'ok'))[1]), \
             mock.patch.object(scheduler, 'send_windows_toast', lambda *a: None):
            scheduler.check_and_send_reminders()
        self.assertEqual(gonderilen, ['FIRST_REMINDER'])


if __name__ == '__main__':
    unittest.main()
