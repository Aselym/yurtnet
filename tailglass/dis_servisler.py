"""Ucretsiz dis veri servisleri: TCMB doviz kuru ve resmi tatiller (Nager.Date).

Ikisi de anahtar istemez. Sonuclar settings ile ayni SQLite'ta onbelleklenir;
bir gun/yil bir kez indirilir. Internet yoksa sessizce bos doner — hicbir
ekran bu servislere bagli olarak bozulmaz.
"""
import json
import threading
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from database import get_db_connection

ZAMAN_ASIMI = 8
_KILIT = threading.Lock()


def _tablo(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS dis_onbellek (anahtar TEXT PRIMARY KEY, deger TEXT NOT NULL)')


def _oku(anahtarlar):
    conn = get_db_connection()
    try:
        _tablo(conn)
        out = {}
        for i in range(0, len(anahtarlar), 500):
            parca = anahtarlar[i:i + 500]
            rows = conn.execute(f"SELECT anahtar, deger FROM dis_onbellek WHERE anahtar IN ({','.join('?' * len(parca))})", parca)
            out.update({r[0]: r[1] for r in rows})
        return out
    finally:
        conn.close()


def _yaz(kayitlar):
    if not kayitlar:
        return
    with _KILIT:
        conn = get_db_connection()
        try:
            _tablo(conn)
            conn.executemany('INSERT OR REPLACE INTO dis_onbellek VALUES (?, ?)', list(kayitlar.items()))
            conn.commit()
        finally:
            conn.close()


def _indir(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'TailglassAnalytics/1.0'})
    with urllib.request.urlopen(req, timeout=ZAMAN_ASIMI) as r:
        return r.read()


# ------------------------------------------------------------------ TCMB
def _tcmb_gun(gun):
    """'YYYY-MM-DD' gunun USD doviz satis kuru; tatil/hafta sonu ya da hata -> None."""
    y, m, d = gun.split('-')
    url = 'https://www.tcmb.gov.tr/kurlar/today.xml' if gun == date.today().isoformat() \
        else f'https://www.tcmb.gov.tr/kurlar/{y}{m}/{d}{m}{y}.xml'
    try:
        kok = ET.fromstring(_indir(url))
    except Exception:
        return None
    for c in kok.iter('Currency'):
        if c.get('CurrencyCode') == 'USD':
            for alan in ('ForexSelling', 'BanknoteSelling'):
                v = (c.findtext(alan) or '').strip()
                if v:
                    return float(v)
    return None


def tcmb_usd_kurlari(gunler):
    """{gun: usd_kuru}. Kur yayimlanmayan gunler (hafta sonu, tatil) sonucta yer almaz;
    cagiran en yakin onceki gunun kurunu kullanir. Onbellekte olmayanlar paralel indirilir."""
    bugun = date.today().isoformat()
    gunler = sorted({g[:10] for g in gunler if g and g[:10] <= bugun})
    if not gunler:
        return {}
    anahtar = lambda g: f'tcmb:USD:{g}'
    onbellek = _oku([anahtar(g) for g in gunler])
    sonuc, eksik = {}, []
    for g in gunler:
        v = onbellek.get(anahtar(g))
        if v is None:
            eksik.append(g)
        elif v != '-':
            sonuc[g] = float(v)
    if eksik:
        with ThreadPoolExecutor(max_workers=8) as ex:
            gelen = dict(zip(eksik, ex.map(_tcmb_gun, eksik)))
        yeni = {}
        for g, v in gelen.items():
            if v is not None:
                sonuc[g] = v
                yeni[anahtar(g)] = str(v)
            elif g < bugun:
                yeni[anahtar(g)] = '-'          # yayim yok (tatil); bugun yeniden denenir
        # hic baglanti yoksa '-' yazip kalici olarak kaybetmeyelim
        if any(v is not None for v in gelen.values()):
            _yaz(yeni)
    return sonuc


# ------------------------------------------------------------------ resmi tatiller
def tatiller(yillar):
    """[{date, ad}] — Turkiye resmi tatil ve bayram gunleri."""
    out = []
    for yil in sorted(set(int(y) for y in yillar)):
        k = f'tatil:TR:{yil}'
        v = _oku([k]).get(k)
        if v is None:
            try:
                ham = json.loads(_indir(f'https://date.nager.at/api/v3/PublicHolidays/{yil}/TR'))
                v = json.dumps([{'date': h['date'], 'ad': h.get('localName') or h.get('name')} for h in ham], ensure_ascii=False)
                _yaz({k: v})
            except Exception:
                continue
        out += json.loads(v)
    return out
