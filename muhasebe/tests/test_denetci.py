"""Denetci: bulgularin gunluge yazilmasi, acil mail siniri, gunluk ozet. Sahte yapay zeka + sahte SMTP."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ['MUHASEBE_DB'] = os.path.join(tempfile.mkdtemp(), 'test.db')

import denetci  # noqa: E402
import mailer  # noqa: E402
from database import get_db_connection, init_db  # noqa: E402

init_db()
CEVAP = {'metin': ''}
GIDEN = []


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        govde = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        GIDEN.append(govde)
        b = json.dumps({'choices': [{'message': {'content': CEVAP['metin']}}]}).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)


class DenetciTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), Sahte)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        ayar = {'ai_provider': 'openai', 'ai_base_url': f'http://127.0.0.1:{cls.srv.server_port}', 'ai_model': 'm',
                'ai_api_key': 'k', 'ai_urgent_limit': '1', 'internal_recipients': 'ekip@ornek.com', 'smtp_host': 'x'}
        conn = get_db_connection()
        conn.executemany('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', list(ayar.items()))
        conn.commit(); conn.close()
        cls.mailler = []
        cls.eski = mailer.smtp_gonder
        mailer.smtp_gonder = lambda ayarlar, alicilar, konu, govde: (cls.mailler.append((alicilar, konu, govde)) or (True, 'ok'))

    @classmethod
    def tearDownClass(cls):
        mailer.smtp_gonder = cls.eski
        cls.srv.shutdown()

    def setUp(self):
        conn = get_db_connection()
        denetci._tablo(conn)
        conn.execute('DELETE FROM asistan_gunlugu'); conn.commit(); conn.close()
        self.mailler.clear(); GIDEN.clear()

    def test_bulgular_gunluk_ve_mail(self):
        CEVAP['metin'] = 'Buyurun: ' + json.dumps({'bulgular': [
            {'onem': 'acil', 'baslik': 'Büyük müşteri sessiz', 'metin': 'X 90 gündür almıyor.'},
            {'onem': 'acil', 'baslik': 'İkinci acil', 'metin': 'Sınır nedeniyle özete gitmeli.'},
            {'onem': 'bilgi', 'baslik': 'Marj sabit', 'metin': 'Marj %35.'},
            {'onem': 'saçma', 'baslik': '', 'metin': 'başlıksız atlanır'}]}, ensure_ascii=False)
        r = denetci.denetle('test')
        self.assertTrue(r['success'], r)
        self.assertEqual(len(r['bulgular']), 3)
        # denetim olcumleri ve rol modele gitti
        sistem = GIDEN[0]['messages'][0]['content']
        self.assertIn('denetçisi', sistem)
        self.assertIn('olcum_bitis_tarihi', GIDEN[0]['messages'][-1]['content'])
        kayit = {k['baslik']: k for k in denetci.gunluk()}
        # gunluk acil siniri 1: ilki hemen, ikincisi ozete
        self.assertEqual(kayit['Büyük müşteri sessiz']['mail'], 'gonderildi')
        self.assertEqual(kayit['İkinci acil']['mail'], 'ozette')
        self.assertEqual(kayit['Marj sabit']['mail'], 'ozette')
        self.assertEqual(len(self.mailler), 1)
        self.assertEqual(self.mailler[0][0], ['ekip@ornek.com'])
        self.assertIn('Acil: Büyük müşteri sessiz', self.mailler[0][1])

        o = denetci.gunluk_ozet_gonder()
        self.assertTrue(o['success'])
        self.assertEqual(len(self.mailler), 2)
        self.assertIn('2 bulgu', self.mailler[1][1])
        self.assertTrue(all(k['mail'] in ('gonderildi', 'ozet_gonderildi') for k in denetci.gunluk()))
        self.assertEqual(denetci.gunluk_ozet_gonder()['message'], 'Özette gönderilecek yeni bulgu yok.')

    def test_bozuk_yanit_hata_kaydi(self):
        CEVAP['metin'] = 'JSON vermiyorum'
        r = denetci.denetle('test')
        self.assertFalse(r['success'])
        self.assertEqual(denetci.gunluk()[0]['kaynak'], 'hata')
        self.assertEqual(self.mailler, [])

    def test_bos_bulgu(self):
        CEVAP['metin'] = '{"bulgular": []}'
        r = denetci.denetle('test')
        self.assertTrue(r['success'])
        self.assertIn('dikkat gerektiren bir şey yok', r['message'])
        self.assertEqual(denetci.gunluk(), [])


if __name__ == '__main__':
    unittest.main()
