"""Arayuz taramasi (gercek tarayici, Edge): her sayfa, her sekme/gorunum dugmesi,
satir detayi, PDF, Excel indirme ve telefon genisliginde yatay tasma.
Konsol hatasi, sayfa istisnasi, hata kutusu ya da 5xx cevap arar.

    pip install playwright openpyxl
    python dev/demo_sunucu.py          # ayri bir pencerede, port 5050
    python tests/arayuz_tarama.py
"""
import os, sys, time
from playwright.sync_api import sync_playwright

B = 'http://localhost:5050'
SAYFALAR = ['studyo', 'genel', 'satislar', 'alislar', 'stok', 'musteriler', 'analiz', 'donem', 'lisanslar', 'abonelikler', 'teklifler', 'temsilciler', 'ayarlar']
SORUN = []


def not_al(sayfa, ne, ayrinti=''):
    SORUN.append((sayfa, ne, str(ayrinti)[:220]))


with sync_playwright() as p:
    br = p.chromium.launch(channel='msedge', headless=True)
    ctx = br.new_context(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    pg = ctx.new_page()
    aktif = {'sayfa': 'giris'}
    pg.on('console', lambda m: m.type == 'error' and '401' not in m.text and not_al(aktif['sayfa'], 'konsol hatası', m.text))
    pg.on('pageerror', lambda e: not_al(aktif['sayfa'], 'sayfa istisnası', e))
    pg.on('response', lambda r: r.status >= 500 and not_al(aktif['sayfa'], f'sunucu {r.status}', r.url))
    pg.on('dialog', lambda d: (not_al(aktif['sayfa'], 'tarayıcı diyalogu', d.message), d.dismiss()))

    pg.goto(B); time.sleep(1)
    pg.locator('#kullanici').fill('admin'); pg.locator('#sifre').fill('Aa123456'); pg.keyboard.press('Enter'); time.sleep(2.5)

    def hata_kutusu():
        for t in ('Tekrar dene', 'Beklenmeyen bir hata', 'Bu sayfa açılırken bir sorun'):
            if pg.get_by_text(t).count():
                not_al(aktif['sayfa'], 'hata kutusu', t)

    for s in SAYFALAR:
        aktif['sayfa'] = s
        pg.goto(f'{B}/#/{s}'); time.sleep(2.5)
        hata_kutusu()
        if not pg.locator('main').inner_text().strip():
            not_al(s, 'boş sayfa')
        # sekme / gorunum dugmeleri (Segmented = role radio); ust cubuktaki para birimi haric
        radyolar = pg.locator('main [role=radio]')
        for i in range(radyolar.count()):
            try:
                r = radyolar.nth(i)
                ad = r.inner_text()
                r.click(timeout=3000); time.sleep(1.2)
                hata_kutusu()
            except Exception as e:
                not_al(s, f'sekme tıklanamadı: {ad!r}', e)
        # ilk tablo satirina tikla (detay / modal / drawer), sonra kapat
        try:
            satir = pg.locator('main [role=row]').nth(1)
            if satir.count():
                satir.click(timeout=3000); time.sleep(1.5)
                hata_kutusu()
                pg.keyboard.press('Escape'); time.sleep(0.5)
        except Exception as e:
            not_al(s, 'satır tıklaması', e)
        # PDF (gizli iframe)
        try:
            pdf = pg.get_by_role('button', name='PDF', exact=True)
            if pdf.count() and pdf.first.is_enabled():
                pdf.first.click(timeout=3000); time.sleep(1)
                if not pg.locator('#tg-yazdir').count():
                    not_al(s, 'PDF çerçevesi oluşmadı')
        except Exception as e:
            not_al(s, 'PDF', e)
        # Kolonlar menusu
        try:
            k = pg.get_by_role('button', name='Kolonlar')
            if k.count():
                k.first.click(timeout=3000); time.sleep(0.5); pg.keyboard.press('Escape')
        except Exception as e:
            not_al(s, 'Kolonlar', e)

    # Excel: sayfa basina bir deneme
    for s, dugme in [('satislar', "Excel'e aktar"), ('stok', 'Excel'), ('musteriler', "Excel'e aktar"), ('analiz', "Excel'e aktar"), ('donem', "Excel'e aktar")]:
        aktif['sayfa'] = s
        pg.goto(f'{B}/#/{s}'); time.sleep(2.5)
        try:
            with pg.expect_download(timeout=60000) as d:
                pg.get_by_role('button', name=dugme, exact=True).first.click()
            if not d.value.suggested_filename.endswith('.xlsx'):
                not_al(s, 'Excel adı', d.value.suggested_filename)
        except Exception as e:
            not_al(s, 'Excel indirilemedi', e)

    # Dar ekran (telefon) — yatay tasma
    ctx2 = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    m = ctx2.new_page()
    m.goto(B); time.sleep(1)
    m.locator('#kullanici').fill('admin'); m.locator('#sifre').fill('Aa123456'); m.keyboard.press('Enter'); time.sleep(2.5)
    for s in SAYFALAR:
        m.goto(f'{B}/#/{s}'); time.sleep(2)
        tasma = m.evaluate("(() => { const e = document.querySelector('main'); return e ? e.scrollWidth - e.clientWidth : 0 })()")
        if tasma > 4:
            not_al(s, 'telefonda yatay taşma', f'{tasma}px')
    br.close()

if SORUN:
    for x in SORUN:
        print('SORUN', *x)
else:
    print('Sorun bulunamadı.')
sys.exit(1 if SORUN else 0)
