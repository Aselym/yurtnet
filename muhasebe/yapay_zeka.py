"""Yapay zeka saglayicisi: stuidyodaki "Sohbet" icin.

Saglayici Ayarlar'dan secilir; kod hicbir saglayiciya bagli degil:
  groq       ucretsiz katman, OpenAI uyumlu arayuz
  anthropic  Claude (ucretli, en iyi Turkce)
  ollama     sirket sunucusunda calisan yerel model; veri disari cikmaz
  openai     baska herhangi bir OpenAI uyumlu servis (adres + anahtar)

Model ekrandaki pano ozetini gorur; ayrica (ai_db_access acikken) ai_araclar.py'deki
beyaz listeli, salt okunur araclarla toplu veri sorgulayabilir ve ongoru isteyebilir.
Ham satir, e-posta, telefon modele gitmez.
"""
import json
import time
import urllib.error
import urllib.request

from database import get_settings

SAGLAYICILAR = {
    'groq': {'ad': 'Groq (ücretsiz katman)', 'adres': 'https://api.groq.com/openai/v1', 'model': 'openai/gpt-oss-120b', 'anahtar': True},
    'anthropic': {'ad': 'Claude (Anthropic)', 'adres': 'https://api.anthropic.com', 'model': 'claude-sonnet-5-5', 'anahtar': True},
    'ollama': {'ad': 'Ollama (yerel)', 'adres': 'http://localhost:11434', 'model': 'qwen2.5:7b', 'anahtar': False},
    'openai': {'ad': 'OpenAI uyumlu', 'adres': '', 'model': '', 'anahtar': True},
}
ZAMAN_ASIMI = 90
AZAMI_BAGLAM = 24000       # karakter
AZAMI_MESAJ = 20
AZAMI_TALIMAT = 2000       # kullanicinin ek talimatlari (Ayarlar)
ARAC_TURU = 6              # bir soruda en fazla bu kadar arac turu

SISTEM = """Sen Tailglass Analytics'in analiz asistanısın. Bir KOBİ yöneticisiyle konuşuyorsun: sorularını yanıtlar, şirketin satış, kâr, stok ve lisans verisini yorumlar, öngörü ve öneri sunarsın. Genel sorularda normal bir sohbet ortağı gibi davranabilirsin.
Kurallar:
- Şirket verisiyle ilgili her rakam ya kullanıcının ekrandaki PANO bölümünden, ŞİRKET PROFİLİ'nden ya da araçlardan (veri_sorgula, tahmin, lisans_bitisleri, abonelikleri_listele, stok_ozeti) gelmeli. Kafandan rakam, müşteri ya da ürün adı uydurma. Gerekirse önce aracı çağır; erişimin yoksa "bu bilgiye erişimim yok" de.
- Önerilerine tahmini etki rakamı ekleme ("%3-5 marj artışı", "5 milyon ₺ ek kâr", "stoğu %10 azaltın" gibi). Bu rakamlar hiçbir veriden gelmez. Öneriyi rakamsız yaz ya da yalnızca verideki gerçek rakama dayandır (ör. "90 gün içinde dolacak lisansların son satış tutarı 800 bin ₺").
- Gelecek hakkında rakam vereceksen tahmin aracını kullan; aralığı (alt-üst) ve yöntemin geçmişteki hata payını da söyle. Öngörünün kesin olmadığını belirt.
- Müşteri ya da ürün adını tam bilmiyorsan önce deger_ara ile bul, sonra filtrele. Adları araçtan geldiği gibi aynen yaz; harf, kısaltma ya da Türkçe karakter düzeltmesi yapma. "Müşteri #594", "Temsilci #12" gibi numaralı adları da aynen (numarasıyla) yaz.
- Türkçe, sade ve kısa yaz; yönetici dili kullan. En fazla birkaç paragraf.
- Tamamen Türkçe yaz (ay adları dahil: Haziran, Temmuz…). Düz metin kullan; ** ya da # gibi biçim işaretleri ve tablo koyma, madde için satır başına "- " yaz.
- Tutarları okunur yuvarla (ör. 187,4 milyon ₺).
- Somut, uygulanabilir öneriler ver; kesin olmayan çıkarımları "olabilir" diye belirt.
"""


class YapayZekaHatasi(Exception):
    def __init__(self, mesaj, kod=None):
        super().__init__(mesaj)
        self.kod = kod


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
            'veritabani': (get_settings().get('ai_db_access') or 'ON') != 'OFF',
            'eksik': 'API anahtarı, adres ya da model eksik.' if eksik else None}


def _post(url, govde, basliklar, deneme=3):
    req = urllib.request.Request(url, data=json.dumps(govde).encode('utf-8'),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'TailglassAnalytics/1.0', **basliklar})
    try:
        with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        kod = e.code
        if kod == 429 and deneme > 1:
            # ucretsiz katmanlarin dakikalik token sinirlari (Groq: 8000/dk): saglayicinin soyledigi kadar bekle
            bekle = 6
            for b in ('retry-after', 'x-ratelimit-reset-tokens'):
                v = (e.headers.get(b) or '').strip().rstrip('s')
                try:
                    bekle = max(bekle, float(v) + 1) if v else bekle
                except ValueError:
                    pass
            if bekle <= 60:
                time.sleep(bekle)
                return _post(url, govde, basliklar, deneme - 1)
        if kod in (401, 403):
            raise YapayZekaHatasi('API anahtarı geçersiz ya da yetkisiz. Ayarlar > Yapay zekâ bölümünü kontrol edin.', kod)
        if kod == 429:
            raise YapayZekaHatasi('Sağlayıcının kullanım sınırına ulaşıldı. Biraz sonra tekrar deneyin.', kod)
        if kod == 404:
            raise YapayZekaHatasi('Model ya da adres bulunamadı. Model adını kontrol edin.', kod)
        raise YapayZekaHatasi(f'Yapay zekâ servisi hata döndürdü (HTTP {kod}).', kod)
    except (urllib.error.URLError, TimeoutError, OSError):
        raise YapayZekaHatasi('Yapay zekâ servisine ulaşılamadı. İnternet bağlantısını ya da adresi kontrol edin.')


def _sistem_metni(ayarlar, baglam, araclar_acik):
    sistem = SISTEM
    if araclar_acik:
        try:
            import ai_veri
            sistem += ('\nŞİRKET PROFİLİ (senkronla gelen verinin özeti; arka plan bilginiz. Ayrıntı için araçları kullanın):\n'
                       + ai_veri.sirket_profili() + '\n')
        except Exception:
            import ai_araclar
            sistem += '\n' + ai_araclar.sistem_bilgisi() + '\n'
    else:
        sistem += '\nVeritabanı araçları kapalı: yalnızca PANO bölümündeki bilgilere dayan.\n'
    talimat = (ayarlar.get('ai_instructions') or '').strip()[:AZAMI_TALIMAT]
    if talimat:
        sistem += '\nŞirketin ek talimatları (yukarıdaki kurallarla çelişmedikçe uy):\n' + talimat + '\n'
    return sistem + '\nPANO (kullanıcının ekranındaki kartlar):\n' + str(baglam or '(pano boş)')[:AZAMI_BAGLAM]


def _arac_ozeti(ad, arg):
    """Arayuzde 'asistan ne sorguladi' satiri icin okunur ozet."""
    if isinstance(arg, str):
        try:
            arg = json.loads(arg or '{}')
        except ValueError:
            arg = {}
    arg = arg if isinstance(arg, dict) else {}
    if ad == 'veri_sorgula':
        parca = [', '.join(arg.get('measures') or ['net_tl'])]
        if arg.get('group_by'):
            parca.append('kırılım: ' + ', '.join(arg['group_by']))
        if arg.get('date_from') or arg.get('date_to'):
            parca.append(f"{arg.get('date_from') or '…'} – {arg.get('date_to') or '…'}")
        if isinstance(arg.get('filters'), dict) and arg['filters']:
            parca.append('filtre: ' + ', '.join(f'{k}={v}' for k, v in arg['filters'].items()))
        return 'Veri sorgusu (' + '; '.join(parca) + ')'
    if ad == 'tahmin':
        return f"Öngörü ({arg.get('measure', 'net_tl')}, {arg.get('ay_sayisi') or 6} ay)"
    if ad == 'lisans_bitisleri':
        return f"Lisans bitişleri ({arg.get('gun') or 90} gün)"
    if ad == 'deger_ara':
        return f"Ad araması ({arg.get('metin', '')})"
    if ad == 'abonelikleri_listele':
        return f"Abonelikler ({arg.get('durum') or 'riskli'})"
    if ad == 'stok_ozeti':
        return f"Stok özeti ({arg.get('tarih') or 'bugün'})"
    return str(ad)


def sohbet(mesajlar, baglam, ayarlar=None):
    """mesajlar: [{'rol': 'kullanici'|'asistan', 'metin': str}]
    Doner: {'yanit': str, 'araclar': [kullanilan araclarin okunur ozeti]}"""
    ayarlar = ayarlar or get_settings()
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
    _hazir_mi(y)
    araclar_acik = (ayarlar.get('ai_db_access') or 'ON') != 'OFF'
    return _maskeli_konus(y, temiz, lambda acik: _sistem_metni(ayarlar, baglam, acik), araclar_acik, ayarlar)


def _hazir_mi(y):
    if SAGLAYICILAR[y['saglayici']]['anahtar'] and not y['anahtar']:
        raise YapayZekaHatasi('API anahtarı girilmemiş. Ayarlar > Yapay zekâ bölümünden ekleyin.')
    if not y['adres'] or not y['model']:
        raise YapayZekaHatasi('Yapay zekâ adresi ya da modeli eksik. Ayarlar > Yapay zekâ bölümünü kontrol edin.')


def gorev(gorev_metni, rol_metni, ayarlar=None):
    """Sohbet disi tek seferlik is (denetci): rol_metni + sirket profili + araclar.
    Doner: {'yanit', 'araclar'}. Yapay zeka kapaliysa YapayZekaHatasi."""
    ayarlar = ayarlar or get_settings()
    y = yapilandirma(ayarlar)
    if not y:
        raise YapayZekaHatasi('Yapay zekâ kapalı.')
    _hazir_mi(y)

    def sistem_uret(acik):
        metin = SISTEM + '\n' + rol_metni + '\n'
        if acik:
            import ai_veri
            metin += '\nŞİRKET PROFİLİ:\n' + ai_veri.sirket_profili() + '\n'
        talimat = (ayarlar.get('ai_instructions') or '').strip()[:AZAMI_TALIMAT]
        if talimat:
            metin += '\nŞirketin ek talimatları (yukarıdaki kurallarla çelişmedikçe uy):\n' + talimat + '\n'
        return metin
    return _maskeli_konus(y, [{'role': 'user', 'content': gorev_metni[:20000]}], sistem_uret,
                          (ayarlar.get('ai_db_access') or 'ON') != 'OFF', ayarlar)


def maske_acik_mi(ayarlar):
    return (ayarlar.get('ai_mask_names') or 'ON') != 'OFF'


def _maskeli_konus(y, temiz, sistem_uret, araclar_acik, ayarlar):
    """Musteri/temsilci adlarini (ayar aciksa) modele gondermeden once gizler, cevapta geri acar.
    Model adlari "Müşteri #594" diye yazdigi icin gercek ad cevaba harfi harfine geri konur."""
    import ai_araclar
    import ai_veri
    m = ai_veri.Maske(maske_acik_mi(ayarlar))
    gizli = [{**x, 'content': m.gizle(x['content'])} for x in temiz]

    def calistir_maskeli(ad, arg):
        if isinstance(arg, str):
            try:
                arg = json.loads(arg or '{}')
            except ValueError:
                arg = {}
        return m.gizle(ai_araclar.calistir(ad, m.ac_deger(arg if isinstance(arg, dict) else {})))

    def bitir(sonuc):
        sonuc['yanit'] = m.ac(sonuc.get('yanit') or '')
        sonuc['araclar'] = [m.ac(a) for a in sonuc.get('araclar') or []]
        return sonuc
    try:
        return bitir(_konus(y, gizli, m.gizle(sistem_uret(araclar_acik)), araclar_acik, calistir_maskeli))
    except YapayZekaHatasi as e:
        if araclar_acik and e.kod == 400:
            # bazi modeller (ozellikle kucuk yerel modeller) arac cagirmayi desteklemez: aracsiz tekrar dene
            sonuc = bitir(_konus(y, gizli, m.gizle(sistem_uret(False)), False, calistir_maskeli))
            sonuc['uyari'] = 'Bu model veritabanı araçlarını desteklemiyor; yalnızca ekrandaki panoya göre yanıtlandı.'
            return sonuc
        raise


def _konus(y, temiz, sistem, araclar_acik, calistirici=None):
    import ai_araclar
    s, kullanilan = y['saglayici'], []
    calistirici = calistirici or ai_araclar.calistir

    def calistir(ad, arg):
        kullanilan.append(_arac_ozeti(ad, arg))
        return calistirici(ad, arg)

    if s == 'anthropic':
        tanim = [{'name': a['ad'], 'description': a['aciklama'], 'input_schema': a['parametreler']} for a in ai_araclar.ARACLAR]
        msj = list(temiz)
        for _ in range(ARAC_TURU + 1):
            govde = {'model': y['model'], 'max_tokens': 1000, 'system': sistem, 'messages': msj}
            if araclar_acik:
                govde['tools'] = tanim
            cevap = _post(f"{y['adres']}/v1/messages", govde, {'x-api-key': y['anahtar'], 'anthropic-version': '2023-06-01'})
            bloklar = cevap.get('content') or []
            cagrilar = [b for b in bloklar if b.get('type') == 'tool_use']
            if not cagrilar or not araclar_acik:
                return {'yanit': ''.join(b.get('text', '') for b in bloklar if b.get('type') == 'text').strip(), 'araclar': kullanilan}
            msj.append({'role': 'assistant', 'content': bloklar})
            msj.append({'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': b['id'],
                                                     'content': calistir(b['name'], b.get('input') or {})} for b in cagrilar]})
        raise YapayZekaHatasi('Asistan çok fazla sorgu yaptı; soruyu daraltıp tekrar deneyin.')

    tanim = [{'type': 'function', 'function': {'name': a['ad'], 'description': a['aciklama'], 'parameters': a['parametreler']}}
             for a in ai_araclar.ARACLAR]
    msj = [{'role': 'system', 'content': sistem}, *temiz]
    for _ in range(ARAC_TURU + 1):
        if s == 'ollama':
            govde = {'model': y['model'], 'stream': False, 'messages': msj}
            if araclar_acik:
                govde['tools'] = tanim
            mesaj = _post(f"{y['adres']}/api/chat", govde, {}).get('message') or {}
        else:   # groq ve diger OpenAI uyumlu servisler
            govde = {'model': y['model'], 'max_tokens': 1000, 'temperature': 0.3, 'messages': msj}
            if araclar_acik:
                govde['tools'] = tanim
            bas = {'Authorization': f"Bearer {y['anahtar']}"} if y['anahtar'] else {}
            cevap = _post(f"{y['adres']}/chat/completions", govde, bas)
            try:
                mesaj = cevap['choices'][0]['message']
            except (KeyError, IndexError, TypeError):
                raise YapayZekaHatasi('Yapay zekâ servisinden beklenmeyen yanıt geldi.')
        cagrilar = mesaj.get('tool_calls') or []
        if not cagrilar or not araclar_acik:
            return {'yanit': (mesaj.get('content') or '').strip(), 'araclar': kullanilan}
        msj.append({'role': 'assistant', 'content': mesaj.get('content') or '', 'tool_calls': cagrilar})
        for c in cagrilar:
            f = c.get('function') or {}
            yanit = {'role': 'tool', 'content': calistir(f.get('name'), f.get('arguments') or {})}
            if c.get('id'):
                yanit['tool_call_id'] = c['id']
            msj.append(yanit)
    raise YapayZekaHatasi('Asistan çok fazla sorgu yaptı; soruyu daraltıp tekrar deneyin.')
