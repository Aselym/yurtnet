"""Yapay zeka saglayicisi: stuidyodaki "Sohbet" icin.

Saglayici Ayarlar'dan secilir; kod hicbir saglayiciya bagli degil:
  groq       ucretsiz katman (Llama), OpenAI uyumlu arayuz
  anthropic  Claude (ucretli, en iyi Turkce)
  ollama     sirket sunucusunda calisan yerel model; veri disari cikmaz
  openai     baska herhangi bir OpenAI uyumlu servis (adres + anahtar)

Modele ham fatura satiri gitmez: yalnizca ekrandaki kartlarin basligi, kural
tabanli yorum cumleleri ve kullanicinin notlari (arayuz hazirlar).
"""
import json
import urllib.error
import urllib.request

from database import get_settings

SAGLAYICILAR = {
    'groq': {'ad': 'Groq (ücretsiz katman)', 'adres': 'https://api.groq.com/openai/v1', 'model': 'llama-3.3-70b-versatile', 'anahtar': True},
    'anthropic': {'ad': 'Claude (Anthropic)', 'adres': 'https://api.anthropic.com', 'model': 'claude-sonnet-5-5', 'anahtar': True},
    'ollama': {'ad': 'Ollama (yerel)', 'adres': 'http://localhost:11434', 'model': 'qwen2.5:7b', 'anahtar': False},
    'openai': {'ad': 'OpenAI uyumlu', 'adres': '', 'model': '', 'anahtar': True},
}
ZAMAN_ASIMI = 90
AZAMI_BAGLAM = 24000       # karakter
AZAMI_MESAJ = 20

SISTEM = """Sen Tailglass Analytics'in analiz asistanısın. Bir KOBİ yöneticisine, ekrandaki analiz panosu hakkında yardım ediyorsun.
Kurallar:
- Yalnızca aşağıdaki PANO bölümündeki bilgilere dayan. Orada olmayan rakam, müşteri ya da ürün uydurma; bilmiyorsan "panoda bu bilgi yok" de ve hangi bloğu eklerlerse görebileceklerini öner (ör. "Müşteri" kırılımı).
- Türkçe, sade ve kısa yaz; yönetici dili kullan. Gerektiğinde madde işareti kullan, en fazla birkaç paragraf.
- Rakamları panodaki biçimiyle aynen kullan.
- Somut, uygulanabilir öneriler ver; ama kesin olmayan çıkarımları "olabilir" diye belirt.

PANO:
"""


class YapayZekaHatasi(Exception):
    pass


def yapilandirma(ayarlar=None):
    a = ayarlar or get_settings()
    s = (a.get('ai_provider') or 'kapali').strip()
    if s not in SAGLAYICILAR:
        return None
    v = SAGLAYICILAR[s]
    return {
        'saglayici': s,
        'adres': ((a.get('ai_base_url') or '').strip() or v['adres']).rstrip('/'),
        'model': (a.get('ai_model') or '').strip() or v['model'],
        'anahtar': (a.get('ai_api_key') or '').strip(),
    }


def durum():
    y = yapilandirma()
    if not y:
        return {'acik': False}
    eksik = (SAGLAYICILAR[y['saglayici']]['anahtar'] and not y['anahtar']) or not y['adres'] or not y['model']
    return {'acik': not eksik, 'saglayici': y['saglayici'], 'ad': SAGLAYICILAR[y['saglayici']]['ad'], 'model': y['model'],
            'eksik': 'API anahtarı, adres ya da model eksik.' if eksik else None}


def _post(url, govde, basliklar):
    req = urllib.request.Request(url, data=json.dumps(govde).encode('utf-8'),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'TailglassAnalytics/1.0', **basliklar})
    try:
        with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        kod = e.code
        if kod in (401, 403):
            raise YapayZekaHatasi('API anahtarı geçersiz ya da yetkisiz. Ayarlar > Yapay zekâ bölümünü kontrol edin.')
        if kod == 429:
            raise YapayZekaHatasi('Sağlayıcının kullanım sınırına ulaşıldı. Biraz sonra tekrar deneyin.')
        if kod == 404:
            raise YapayZekaHatasi('Model ya da adres bulunamadı. Model adını kontrol edin.')
        raise YapayZekaHatasi(f'Yapay zekâ servisi hata döndürdü (HTTP {kod}).')
    except (urllib.error.URLError, TimeoutError, OSError):
        raise YapayZekaHatasi('Yapay zekâ servisine ulaşılamadı. İnternet bağlantısını ya da adresi kontrol edin.')


def sohbet(mesajlar, baglam, ayarlar=None):
    """mesajlar: [{'rol': 'kullanici'|'asistan', 'metin': str}] -> yanit metni."""
    y = yapilandirma(ayarlar)
    if not y:
        raise YapayZekaHatasi('Yapay zekâ kapalı. Ayarlar > Yapay zekâ bölümünden bir sağlayıcı seçin.')
    temiz = []
    for m in (mesajlar or [])[-AZAMI_MESAJ:]:
        metin = str(m.get('metin') or '').strip()[:4000]
        if metin:
            temiz.append({'role': 'assistant' if m.get('rol') == 'asistan' else 'user', 'content': metin})
    if not temiz or temiz[-1]['role'] != 'user':
        raise ValueError('Soru boş.')
    s = y['saglayici']
    if SAGLAYICILAR[s]['anahtar'] and not y['anahtar']:
        raise YapayZekaHatasi('API anahtarı girilmemiş. Ayarlar > Yapay zekâ bölümünden ekleyin.')
    if not y['adres'] or not y['model']:
        raise YapayZekaHatasi('Yapay zekâ adresi ya da modeli eksik. Ayarlar > Yapay zekâ bölümünü kontrol edin.')
    sistem = SISTEM + str(baglam or '(pano boş)')[:AZAMI_BAGLAM]

    if s == 'anthropic':
        cevap = _post(f"{y['adres']}/v1/messages",
                      {'model': y['model'], 'max_tokens': 1200, 'system': sistem, 'messages': temiz},
                      {'x-api-key': y['anahtar'], 'anthropic-version': '2023-06-01'})
        return ''.join(b.get('text', '') for b in cevap.get('content', []) if b.get('type') == 'text').strip()

    if s == 'ollama':
        cevap = _post(f"{y['adres']}/api/chat",
                      {'model': y['model'], 'stream': False, 'messages': [{'role': 'system', 'content': sistem}, *temiz]}, {})
        return (cevap.get('message') or {}).get('content', '').strip()

    # groq ve diger OpenAI uyumlu servisler
    bas = {'Authorization': f"Bearer {y['anahtar']}"} if y['anahtar'] else {}
    cevap = _post(f"{y['adres']}/chat/completions",
                  {'model': y['model'], 'max_tokens': 1200, 'temperature': 0.3,
                   'messages': [{'role': 'system', 'content': sistem}, *temiz]}, bas)
    try:
        return cevap['choices'][0]['message']['content'].strip()
    except (KeyError, IndexError, TypeError):
        raise YapayZekaHatasi('Yapay zekâ servisinden beklenmeyen yanıt geldi.')
