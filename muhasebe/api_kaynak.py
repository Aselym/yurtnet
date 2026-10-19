"""Veri kaynagi baglama uclari: dosya yukleme, otomatik esleme, onay.

Akis (Ayarlar > Veri kaynagi):
  1. Kullanici Excel/CSV ya da e-Fatura (XML/ZIP) yukler  -> /api/kaynak/yukle
  2. Tablo ise kolonlar otomatik eslenir, guven puani ve gerekce doner;
     kullanici duzeltip onaylar                            -> /api/kaynak/esleme
     e-Fatura ise sirket vergi no'su otomatik bulunur      -> /api/kaynak/efatura-onayla
  3. Kaynak secilir ve senkron baslar; tum ekranlar yeni veriyle calisir.
Dosyalar sunucunun kendi diskinde durur, hicbir yere gonderilmez.
"""

import json
import os
import re
import shutil
import urllib.parse

from database import get_db_connection, get_settings
import esleme
import kaynaklar
import kaynak_dosya
import kaynak_efatura

YUKLEME_AZAMI = 300 * 1024 * 1024
TABLO_UZANTI = ('.xlsx', '.xlsm', '.csv', '.txt', '.tsv')
EFATURA_UZANTI = ('.xml', '.zip')


def _guvenli_ad(ad):
    ad = os.path.basename(ad or 'dosya')
    ad = re.sub(r'[^\w.\- ]+', '_', ad, flags=re.UNICODE).strip() or 'dosya'
    return ad[:120]


def _ayar_yaz(**degerler):
    conn = get_db_connection()
    try:
        for k, v in degerler.items():
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, v))
        conn.commit()
    finally:
        conn.close()


def _tablo_analizi(dosya, sayfa=None):
    yol = os.path.join(kaynaklar.DOSYA_KLASORU, dosya)
    sayfalar, secilen, basliklar, satirlar = kaynak_dosya.tablo_oku(yol, sayfa, en_fazla=400)
    oneri, profiller = esleme.oner(basliklar, satirlar)
    return {
        'tur': 'tablo', 'dosya': dosya, 'sayfalar': sayfalar, 'sayfa': secilen, 'basliklar': basliklar,
        'onizleme': [[('' if v is None else str(v))[:60] for v in r[:len(basliklar)]] for r in satirlar[:8]],
        'ornekler': [p['ornek'] for p in profiller],
        'oneri': oneri, 'eksik': esleme.eksikler(oneri),
        'alanlar': [{'key': k, 'label': v[0], 'zorunlu': v[2]} for k, v in esleme.ALANLAR.items()],
    }


def kaynak_yukle(h, query, veri):
    q = {k: v[0] for k, v in urllib.parse.parse_qs(query or '').items()}
    ad = _guvenli_ad(urllib.parse.unquote(h.headers.get('X-Dosya-Adi') or q.get('ad') or 'dosya'))
    uzanti = os.path.splitext(ad)[1].lower()
    try:
        if uzanti in TABLO_UZANTI:
            # Tek aktif tablo: oncekiler silinir
            if os.path.isdir(kaynaklar.DOSYA_KLASORU):
                shutil.rmtree(kaynaklar.DOSYA_KLASORU)
            os.makedirs(kaynaklar.DOSYA_KLASORU)
            with open(os.path.join(kaynaklar.DOSYA_KLASORU, ad), 'wb') as f:
                f.write(veri)
            h._send_json({'success': True, **_tablo_analizi(ad)})
        elif uzanti in EFATURA_UZANTI:
            # e-Fatura birikir: aylik arsivler ayri ayri yuklenebilir
            os.makedirs(kaynaklar.EFATURA_KLASORU, exist_ok=True)
            with open(os.path.join(kaynaklar.EFATURA_KLASORU, ad), 'wb') as f:
                f.write(veri)
            oz = kaynak_efatura.ozet(kaynaklar.EFATURA_KLASORU, (get_settings().get('efatura_vkn') or '').strip() or None)
            if not oz['faturalar']:
                h._send_json({'success': False, 'message': 'Dosyada UBL-TR biçiminde e-Fatura bulunamadı.', **oz}, 400)
                return
            h._send_json({'success': True, 'tur': 'efatura', 'dosya': ad, **oz,
                          'dosyalar': sorted(os.listdir(kaynaklar.EFATURA_KLASORU))})
        else:
            h._send_json({'success': False, 'message': 'Desteklenen dosyalar: Excel (.xlsx), CSV, e-Fatura XML ya da ZIP.'}, 400)
    except (ValueError, KeyError, OSError) as e:
        print(f'[Kaynak yukleme] {e}')
        h._send_json({'success': False, 'message': f'Dosya okunamadı: {e}'}, 400)


def handle(h, method, path, body):
    """api_v2'den cagrilir. Doner: cevaplandiysa True."""
    if method == 'GET' and path == '/api/kaynak/durum':
        a = get_settings()
        mod = a.get('logo_source') or 'mssql'
        e = kaynaklar.esleme_ayari(a)
        ef = sorted(os.listdir(kaynaklar.EFATURA_KLASORU)) if os.path.isdir(kaynaklar.EFATURA_KLASORU) else []
        h._send_json({'mod': mod, 'ad': kaynaklar.KAYNAK_ADI.get(mod, mod), 'tablo': e.get('dosya'),
                      'efatura_dosyalari': ef, 'efatura_vkn': a.get('efatura_vkn') or ''})
        return True
    if method == 'POST' and path == '/api/kaynak/analiz':
        e = kaynaklar.esleme_ayari(get_settings())
        dosya = body.get('dosya') or e.get('dosya')
        if not dosya or not os.path.exists(os.path.join(kaynaklar.DOSYA_KLASORU, dosya)):
            h._send_json({'success': False, 'message': 'Önce bir tablo dosyası yükleyin.'}, 400)
            return True
        sonuc = _tablo_analizi(dosya, body.get('sayfa'))
        if not body.get('sayfa') and e.get('dosya') == dosya and e.get('esleme'):
            sonuc['kayitli'] = e['esleme']                 # daha once onaylanmis esleme
        h._send_json({'success': True, **sonuc})
        return True
    if method == 'POST' and path == '/api/kaynak/esleme':
        dosya = _guvenli_ad(body.get('dosya'))
        e = {k: int(v) for k, v in (body.get('esleme') or {}).items() if k in esleme.ALANLAR and v not in (None, '')}
        eksik = esleme.eksikler(e)
        if eksik:
            h._send_json({'success': False, 'message': 'Eksik alan: ' + ', '.join(eksik)}, 400)
            return True
        ayar = {'dosya': dosya, 'sayfa': body.get('sayfa'), 'esleme': e,
                'varsayilan_yon': body.get('varsayilan_yon') if body.get('varsayilan_yon') in ('SATIS', 'ALIS') else 'SATIS'}
        # Kaydetmeden once dene: okunabiliyor mu, kac satir atlaniyor?
        k = kaynak_dosya.DosyaKaynagi(ayar, kaynaklar.DOSYA_KLASORU)
        with k:
            ornek = list(k.satirlar())
        if not ornek:
            h._send_json({'success': False, 'message': 'Bu eşlemeyle hiç satır okunamadı. Tarih, ürün ve tutar kolonlarını kontrol edin.'}, 400)
            return True
        _ayar_yaz(dosya_esleme=json.dumps(ayar, ensure_ascii=False), logo_source='dosya')
        from api_v2 import senkron_baslat
        senkron_baslat()
        yonler = {}
        for s in ornek:
            yonler[s['trcode']] = yonler.get(s['trcode'], 0) + 1
        h._send_json({'success': True, 'satir': len(ornek), 'atlanan': k.atlanan,
                      'message': f'{len(ornek):,} satır okunacak; senkron başladı.'
                                 + (f' {k.atlanan:,} satır tarih/ürün/tutar eksik olduğu için atlandı.' if k.atlanan else '')})
        return True
    if method == 'POST' and path == '/api/kaynak/efatura-ozet':
        if not os.path.isdir(kaynaklar.EFATURA_KLASORU) or not os.listdir(kaynaklar.EFATURA_KLASORU):
            h._send_json({'success': True, 'faturalar': 0, 'dosyalar': []})
            return True
        vkn = re.sub(r'\D', '', str(body.get('vkn') or get_settings().get('efatura_vkn') or '')) or None
        h._send_json({'success': True, **kaynak_efatura.ozet(kaynaklar.EFATURA_KLASORU, vkn),
                      'dosyalar': sorted(os.listdir(kaynaklar.EFATURA_KLASORU))})
        return True
    if method == 'POST' and path == '/api/kaynak/efatura-onayla':
        vkn = re.sub(r'\D', '', str(body.get('vkn') or ''))
        _ayar_yaz(efatura_vkn=vkn, logo_source='efatura')
        from api_v2 import senkron_baslat
        senkron_baslat()
        h._send_json({'success': True, 'message': 'e-Fatura kaynağı seçildi; senkron başladı.'})
        return True
    if method == 'DELETE' and path == '/api/kaynak/efatura':
        if os.path.isdir(kaynaklar.EFATURA_KLASORU):
            shutil.rmtree(kaynaklar.EFATURA_KLASORU)
        h._send_json({'success': True, 'message': 'Yüklenen e-Fatura dosyaları kaldırıldı.'})
        return True
    return False
