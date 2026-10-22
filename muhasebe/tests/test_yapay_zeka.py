"""Yapay zeka saglayicilari: sahte yerel sunucuyla istek bicimi ve hata mesajlari."""
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yapay_zeka as yz

GELEN = []


class Sahte(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        govde = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        GELEN.append((self.path, dict(self.headers), govde))
        if 'bozuk' in self.path:
            self.send_response(401); self.end_headers(); return
        if self.path.endswith('/chat/completions'):
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
        self.assertEqual(yz.sohbet(self.MSJ, 'PANO-OZETI', self.a('groq')), 'openai yanıtı')
        yol, bas, govde = GELEN[0]
        self.assertEqual(yol, '/chat/completions')
        self.assertEqual(bas['Authorization'], 'Bearer gizli')
        self.assertEqual(govde['messages'][0]['role'], 'system')
        self.assertIn('PANO-OZETI', govde['messages'][0]['content'])
        self.assertEqual(govde['messages'][-1], {'role': 'user', 'content': 'Neden düştü?'})

    def test_ek_talimat(self):
        a = {**self.a('groq'), 'ai_instructions': 'Her cevaba Merhaba ile başla.'}
        yz.sohbet(self.MSJ, 'PANO-OZETI', a)
        sistem = GELEN[0][2]['messages'][0]['content']
        self.assertIn('Merhaba ile başla', sistem)
        self.assertLess(sistem.index('Merhaba'), sistem.index('PANO-OZETI'))   # pano en sonda

    def test_anthropic(self):
        self.assertEqual(yz.sohbet(self.MSJ, 'x', self.a('anthropic')), 'claude yanıtı')
        yol, bas, govde = GELEN[0]
        self.assertEqual(yol, '/v1/messages')
        self.assertEqual(bas['X-Api-Key'], 'gizli')
        self.assertIn('x', govde['system'])
        self.assertEqual(govde['messages'], [{'role': 'user', 'content': 'Neden düştü?'}])

    def test_ollama_anahtarsiz(self):
        self.assertEqual(yz.sohbet(self.MSJ, 'x', self.a('ollama', anahtar='')), 'ollama yanıtı')
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


if __name__ == '__main__':
    unittest.main()
