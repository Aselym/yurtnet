"""Yapay zeka saglayicilari: sahte yerel sunucuyla istek bicimi ve hata mesajlari."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# gecici, bos veritabani: canli veriye dokunulmaz
os.environ['MUHASEBE_DB'] = os.path.join(tempfile.mkdtemp(), 'test.db')

import ai_araclar  # noqa: E402
import yapay_zeka as yz  # noqa: E402
from database import init_db  # noqa: E402

init_db()

GELEN = []


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        govde = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        GELEN.append((self.path, dict(self.headers), govde))
        if 'bozuk' in self.path:
            self.send_response(401); self.end_headers(); return
        if self.path.endswith('/chat/completions') and 'arac' in self.path:
            # ilk turda arac cagrisi, arac sonucu gelince son yanit
            if govde['messages'][-1]['role'] == 'tool':
                cevap = {'choices': [{'message': {'content': 'lisans yok'}}]}
            else:
                cevap = {'choices': [{'message': {'content': None, 'tool_calls': [
                    {'id': 'c1', 'type': 'function', 'function': {'name': 'lisans_bitisleri', 'arguments': '{"gun": 30}'}}]}}]}
        elif self.path.endswith('/chat/completions') and 'maske' in self.path:
            cevap = {'choices': [{'message': {'content': 'Müşteri #77 öne çıkıyor.'}}]}
        elif self.path.endswith('/chat/completions'):
            cevap = {'choices': [{'message': {'content': ' openai yanıtı '}}]}
        elif self.path.endswith('/v1/messages'):
            cevap = {'content': [{'type': 'text', 'text': 'claude yanıtı'}]}
        else:
            cevap = {'message': {'content': 'ollama yanıtı'}}
        b = json.dumps(cevap).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)


class YapayZekaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(('127.0.0.1', 0), Sahte)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.adres = f'http://127.0.0.1:{cls.srv.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        GELEN.clear()

    def a(self, saglayici, **k):
        return {'ai_provider': saglayici, 'ai_base_url': k.get('adres', self.adres), 'ai_model': 'm', 'ai_api_key': k.get('anahtar', 'gizli')}

    MSJ = [{'rol': 'kullanici', 'metin': 'Neden düştü?'}]

    def test_openai_uyumlu(self):
        self.assertEqual(yz.sohbet(self.MSJ, 'PANO-OZETI', self.a('groq'))['yanit'], 'openai yanıtı')
        yol, bas, govde = GELEN[0]
        self.assertEqual(yol, '/chat/completions')
        self.assertEqual(bas['Authorization'], 'Bearer gizli')
        self.assertEqual(govde['messages'][0]['role'], 'system')
        self.assertIn('PANO-OZETI', govde['messages'][0]['content'])
        self.assertEqual(govde['messages'][-1], {'role': 'user', 'content': 'Neden düştü?'})

    def test_ad_maskeleme(self):
        from database import get_db_connection
        conn = get_db_connection()
        conn.execute("INSERT OR REPLACE INTO wh_clients (client_ref, code, name) VALUES (77, 'C77', 'ORNEK MAKINA A.S.')")
        conn.commit(); conn.close()
        soru = [{'rol': 'kullanici', 'metin': 'ORNEK MAKINA A.S. neden önemli?'}]
        # acik (varsayilan): gercek ad saglayiciya gitmez, cevapta geri acilir
        r = yz.sohbet(soru, 'pano: ORNEK MAKINA A.S. 5 milyon', self.a('openai', adres=self.adres + '/maske'))
        govde = json.dumps(GELEN[-1][2], ensure_ascii=False)
        self.assertNotIn('ORNEK MAKINA', govde)
        self.assertIn('Müşteri #77', govde)
        self.assertEqual(r['yanit'], 'ORNEK MAKINA A.S. öne çıkıyor.')
        # kapali: ad oldugu gibi gider
        yz.sohbet(soru, '', {**self.a('openai', adres=self.adres + '/maske'), 'ai_mask_names': 'OFF'})
        self.assertIn('ORNEK MAKINA A.S.', json.dumps(GELEN[-1][2], ensure_ascii=False))

    def test_ek_talimat(self):
        a = {**self.a('groq'), 'ai_instructions': 'Her cevaba Merhaba ile başla.'}
        yz.sohbet(self.MSJ, 'PANO-OZETI', a)
        sistem = GELEN[0][2]['messages'][0]['content']
        self.assertIn('Merhaba ile başla', sistem)
        self.assertLess(sistem.index('Merhaba'), sistem.index('PANO-OZETI'))   # pano en sonda

    def test_arac_dongusu(self):
        r = yz.sohbet(self.MSJ, 'x', self.a('openai', adres=self.adres + '/arac'))
        self.assertEqual(r['yanit'], 'lisans yok')
        self.assertEqual(r['araclar'], ['Lisans bitişleri (30 gün)'])
        ikinci = GELEN[1][2]['messages']
        self.assertEqual(ikinci[-2]['tool_calls'][0]['id'], 'c1')
        self.assertEqual(ikinci[-1]['role'], 'tool')
        self.assertEqual(ikinci[-1]['tool_call_id'], 'c1')
        self.assertEqual(json.loads(ikinci[-1]['content'])['adet'], 0)

    def test_veritabani_kapali(self):
        a = {**self.a('groq'), 'ai_db_access': 'OFF'}
        yz.sohbet(self.MSJ, 'x', a)
        self.assertNotIn('tools', GELEN[0][2])
        self.assertIn('Veritabanı araçları kapalı', GELEN[0][2]['messages'][0]['content'])

    def test_anthropic(self):
        self.assertEqual(yz.sohbet(self.MSJ, 'x', self.a('anthropic'))['yanit'], 'claude yanıtı')
        yol, bas, govde = GELEN[0]
        self.assertEqual(yol, '/v1/messages')
        self.assertEqual(bas['X-Api-Key'], 'gizli')
        self.assertIn('x', govde['system'])
        self.assertEqual(govde['messages'], [{'role': 'user', 'content': 'Neden düştü?'}])
        self.assertEqual({t['name'] for t in govde['tools']}, {'veri_sorgula', 'deger_ara', 'tahmin', 'lisans_bitisleri', 'abonelikleri_listele', 'stok_ozeti'})

    def test_ollama_anahtarsiz(self):
        self.assertEqual(yz.sohbet(self.MSJ, 'x', self.a('ollama', anahtar=''))['yanit'], 'ollama yanıtı')
        self.assertEqual(GELEN[0][0], '/api/chat')

    def test_hatalar(self):
        with self.assertRaisesRegex(yz.YapayZekaHatasi, 'kapalı'):
            yz.sohbet(self.MSJ, '', {'ai_provider': 'kapali'})
        with self.assertRaisesRegex(yz.YapayZekaHatasi, 'girilmemiş'):
            yz.sohbet(self.MSJ, '', self.a('groq', anahtar=''))
        with self.assertRaisesRegex(yz.YapayZekaHatasi, 'geçersiz'):
            yz.sohbet(self.MSJ, '', self.a('openai', adres=self.adres + '/bozuk'))
        with self.assertRaisesRegex(yz.YapayZekaHatasi, 'ulaşılamadı'):
            yz.sohbet(self.MSJ, '', self.a('openai', adres='http://127.0.0.1:9'))
        with self.assertRaises(ValueError):
            yz.sohbet([], '', self.a('groq'))
        self.assertEqual(GELEN, [g for g in GELEN if 'bozuk' in g[0]])   # anahtarsiz istek gitmedi


class AracTest(unittest.TestCase):
    def test_bilinmeyen_ve_bozuk(self):
        self.assertIn('Bilinmeyen', ai_araclar.calistir('sil', {}))
        self.assertIn('hata', ai_araclar.calistir('veri_sorgula', {'group_by': ['yok'], 'measures': ['DROP TABLE']}) + 'hata')
        self.assertIn('lisanslar', ai_araclar.calistir('lisans_bitisleri', '{bozuk json'))

    def test_mevsimsel_ongoru(self):
        # 3 yil, her yil %10 buyuyen, Aralik'ta zirve yapan seri
        seri = []
        for y in range(3):
            seri += [100 * 1.1 ** y * (2 if m == 11 else 1) for m in range(12)]
        degerler, yontem = ai_araclar._ongor(seri, 12)
        self.assertEqual(yontem, 'mevsimsel')
        self.assertAlmostEqual(degerler[11], 200 * 1.1 ** 3, delta=1)   # bir sonraki Aralik zirvesi
        self.assertAlmostEqual(degerler[0], 100 * 1.1 ** 3, delta=1)

    def test_trend_ongoru(self):
        degerler, yontem = ai_araclar._ongor([10, 20, 30, 40, 50, 60, 70, 80], 2)
        self.assertEqual(yontem, 'trend')
        self.assertAlmostEqual(degerler[0], 90, delta=0.01)
        self.assertAlmostEqual(degerler[1], 100, delta=0.01)


if __name__ == '__main__':
    unittest.main()
