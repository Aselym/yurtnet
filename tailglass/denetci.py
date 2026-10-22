"""7/24 denetci: her senkrondan sonra sirketin hareketini tarar, onemli olani bildirir.

Akis:
  1. sinyaller()  — kural tabanli olcumler (bu ay / gecen yil, son hafta, marj, kaybolan
     buyuk musteriler, buyuk faturalar, iade orani, dolacak lisanslar, riskli abonelikler).
     Burada karar verilmez, yalnizca rakam toplanir.
  2. Yapay zeka bu olcumleri sirket profiliyle birlikte okur, gerekirse araclarla
     derinlestirir ve gercekten dikkat isteyenleri "acil / onemli / bilgi" olarak yazar.
  3. Her bulgu asistan_gunlugu tablosuna yazilir (arayuzde Asistan gunlugu).
  4. Acil olanlar ic alicilara hemen mail olur (gunde en fazla ai_urgent_limit);
     digerleri ai_digest_hour saatinde tek bir gunluk ozet mailinde toplanir.

Mail yalnizca Ayarlar > E-posta'daki ic alicilara gider; musteriye asla gitmez.
Denetci veriyi degistirmez, Logo'ya baglanmaz.
"""
import html
import json
import re
import threading
from datetime import date, datetime, timedelta

import analytics
import yapay_zeka
from database import get_db_connection, get_settings

_KILIT = threading.Lock()

ROL = """Şu an sohbet etmiyorsun; şirketin 7/24 denetçisi olarak çalışıyorsun. Görevin, yöneticinin bilmesi gereken
gelişmeleri yakalamak: satış ya da kârda olağan dışı değişim, büyük müşteri kaybı riski, marj erimesi, iade artışı,
yaklaşan yüksek tutarlı lisans bitişleri, faturası kesilmeyen abonelikler, stok/alış dengesizliği.
Gürültü üretme: sıradan dalgalanmayı, zaten bilinen ya da son günlerde bildirilmiş konuyu tekrar yazma.
Önem dereceleri:
- acil: bugün aksiyon gerektirir (ör. en büyük müşterilerden biri aylardır almıyor, satış sert ve açıklanamaz biçimde düştü,
  birkaç gün içinde yüksek tutarlı lisanslar doluyor).
- onemli: bu hafta ele alınmalı.
- bilgi: bilinmesi yararlı gelişme.
Yanıtın YALNIZCA şu biçimde JSON olsun, başka metin yazma:
{"bulgular": [{"onem": "acil|onemli|bilgi", "baslik": "kısa başlık", "metin": "2-4 cümle; rakamlarla ve önerilen aksiyonla"}]}
Dikkat gerektiren bir şey yoksa {"bulgular": []} döndür."""


# ------------------------------------------------------------------ tablo
def _tablo(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS asistan_gunlugu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zaman TEXT NOT NULL,
        onem TEXT NOT NULL,            -- acil | onemli | bilgi
        baslik TEXT NOT NULL,
        metin TEXT NOT NULL,
        kaynak TEXT NOT NULL DEFAULT 'denetim',
        mail TEXT NOT NULL DEFAULT '', -- gonderildi | ozette | ozet_gonderildi | gonderilemedi: ...
        ozet_zamani TEXT)""")


def gunluk(limit=200):
    conn = get_db_connection()
    try:
        _tablo(conn)
        return [dict(r) for r in conn.execute('SELECT * FROM asistan_gunlugu ORDER BY id DESC LIMIT ?', (int(limit),))]
    finally:
        conn.close()


def _kaydet(onem, baslik, metin, kaynak='denetim', mail=''):
    conn = get_db_connection()
    try:
        _tablo(conn)
        cur = conn.execute('INSERT INTO asistan_gunlugu (zaman, onem, baslik, metin, kaynak, mail) VALUES (?,?,?,?,?,?)',
                           (datetime.now().isoformat(timespec='seconds'), onem, baslik[:200], metin[:4000], kaynak, mail))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _mail_durumu(kimlik, durum, ozet=False):
    conn = get_db_connection()
    try:
        if ozet:
            conn.execute('UPDATE asistan_gunlugu SET mail = ?, ozet_zamani = ? WHERE id = ?',
                         (durum, datetime.now().isoformat(timespec='seconds'), kimlik))
        else:
            conn.execute('UPDATE asistan_gunlugu SET mail = ? WHERE id = ?', (durum, kimlik))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ sinyaller
def _q(**istek):
    return analytics.sorgu(istek)


def _toplam(r, olcu='net_tl'):
    return r['totals'].get(f'm_{olcu}') or 0


def _yuzde(a, b):
    return round(100.0 * (a - b) / abs(b), 1) if b else None


def sinyaller(bugun=None):
    """Kural tabanli olcumler; yapay zekaya JSON olarak gider.

    Pencereler verinin son gunune gore kurulur: senkron birkac gun aksarsa "son 7 gunde
    satis cokmus" gibi yanlis alarm uretilmez (yanlis uyari, hic uyarmamaktan kotudur)."""
    ar = analytics.veri_araligi()
    gercek_bugun = date.today()
    veri_son = date.fromisoformat(ar['last'][:10]) if ar.get('last') else gercek_bugun
    bugun = bugun or min(gercek_bugun, veri_son)
    g = lambda n: (bugun - timedelta(days=n)).isoformat()
    b = bugun.isoformat()
    s = {'bugun': gercek_bugun.isoformat(), 'olcum_bitis_tarihi': b, 'verideki_son_hareket': ar.get('last'),
         'son_senkron': ((ar.get('last_sync') or {}).get('finished_at'))}
    gecikme = (gercek_bugun - veri_son).days
    if gecikme >= 2:
        s['uyari'] = (f'Verideki son hareket {gecikme} gün önce. Ölçümler o güne kadar hesaplandı; senkron aksamış olabilir. '
                      'Bunu satış düşüşü sanma; gerekirse "veri güncel değil" diye bilgi notu yaz.')

    # 1. bu ay (ay basindan bugune) / gecen yilin ayni donemi / son 3 ayin ayni gun dilimi ortalamasi
    ay_bas = bugun.replace(day=1)
    gun_no = bugun.day
    bu_ay = _q(measures=['net_tl', 'profit_tl', 'margin'], date_from=ay_bas.isoformat(), date_to=b)
    try:
        gy = ay_bas.replace(year=ay_bas.year - 1)
        gecen_yil = _q(measures=['net_tl', 'profit_tl'], date_from=gy.isoformat(),
                       date_to=(gy + timedelta(days=gun_no - 1)).isoformat())
    except ValueError:
        gecen_yil = None
    onceki = []
    ay = ay_bas
    for _ in range(3):
        ay = (ay - timedelta(days=1)).replace(day=1)
        onceki.append(_toplam(_q(measures=['net_tl'], date_from=ay.isoformat(),
                                 date_to=(ay + timedelta(days=gun_no - 1)).isoformat())))
    ort3 = sum(onceki) / 3
    s['bu_ay_ilk_gunler'] = {
        'gun_sayisi': gun_no, 'satis_tl': round(_toplam(bu_ay)), 'kar_tl': round(_toplam(bu_ay, 'profit_tl')),
        'marj_yuzde': round(_toplam(bu_ay, 'margin') or 0, 1),
        'gecen_yil_ayni_donem_satis_tl': round(_toplam(gecen_yil)) if gecen_yil else None,
        'gecen_yila_gore_degisim_yuzde': _yuzde(_toplam(bu_ay), _toplam(gecen_yil)) if gecen_yil else None,
        'son_3_ayin_ayni_gun_dilimi_ortalamasi_tl': round(ort3),
        'son_3_aya_gore_degisim_yuzde': _yuzde(_toplam(bu_ay), ort3)}

    # 2. son 7 gun / onceki 8 haftanin haftalik ortalamasi
    son7 = _toplam(_q(measures=['net_tl'], date_from=g(6), date_to=b))
    once8 = _toplam(_q(measures=['net_tl'], date_from=g(62), date_to=g(7))) / 8
    s['son_7_gun'] = {'satis_tl': round(son7), 'onceki_8_haftanin_haftalik_ortalamasi_tl': round(once8),
                      'degisim_yuzde': _yuzde(son7, once8)}

    # 3. marj: son 30 gun / onceki 180 gun
    m30 = _toplam(_q(measures=['margin'], date_from=g(29), date_to=b), 'margin')
    m180 = _toplam(_q(measures=['margin'], date_from=g(209), date_to=g(30)), 'margin')
    s['kar_marji'] = {'son_30_gun_yuzde': round(m30 or 0, 1), 'onceki_6_ay_yuzde': round(m180 or 0, 1),
                      'fark_puan': round((m30 or 0) - (m180 or 0), 1)}

    # 4. son 12 ayin en buyuk 30 musterisinden son 60 gunde alim yapmayanlar
    buyukler = _q(group_by=['client'], measures=['net_tl'], date_from=g(365), date_to=b, limit=30)['rows']
    son60 = {r['d0'] for r in _q(group_by=['client'], measures=['net_tl'], date_from=g(59), date_to=b)['rows']}
    sessiz = [r for r in buyukler if r['d0'] not in son60]
    if sessiz:
        conn = get_db_connection()
        try:
            son_tarih = {r[0]: r[1] for r in conn.execute(
                f"""SELECT c.name, MAX(l.date) FROM wh_lines l JOIN wh_clients c ON c.client_ref = l.client_ref
                    WHERE l.direction = 'SATIS' AND l.cancelled = 0 AND c.name IN ({','.join('?' * len(sessiz))})
                    GROUP BY c.name""", [r['d0'] for r in sessiz])}
        finally:
            conn.close()
        s['sessizlesen_buyuk_musteriler'] = [
            {'musteri': r['d0'], 'son_12_ay_satis_tl': round(r['m_net_tl'] or 0), 'son_alim': son_tarih.get(r['d0'])}
            for r in sessiz[:10]]

    # 5. son 3 gunun en buyuk faturalari (12 aylik ortalama fatura ile birlikte)
    conn = get_db_connection()
    try:
        faturalar = conn.execute("""SELECT l.fiche_no, l.date, c.name, SUM(l.net_tl) AS tutar,
                                           100.0*SUM(CASE WHEN l.cost_complete=1 THEN l.net_tl-l.cost_tl END)
                                               /NULLIF(SUM(CASE WHEN l.cost_complete=1 THEN l.net_tl END),0) AS marj
                                    FROM wh_lines l LEFT JOIN wh_clients c ON c.client_ref = l.client_ref
                                    WHERE l.direction = 'SATIS' AND l.cancelled = 0 AND l.date BETWEEN ? AND ?
                                    GROUP BY l.inv_ref ORDER BY tutar DESC LIMIT 5""", (g(2), b)).fetchall()
        ort = conn.execute("""SELECT AVG(t) FROM (SELECT SUM(net_tl) AS t FROM wh_lines WHERE direction = 'SATIS'
                              AND cancelled = 0 AND date BETWEEN ? AND ? GROUP BY inv_ref)""", (g(365), b)).fetchone()[0]
    finally:
        conn.close()
    if faturalar:
        s['son_3_gunun_en_buyuk_faturalari'] = {
            'ortalama_fatura_12_ay_tl': round(ort or 0),
            'faturalar': [{'fis': f[0], 'tarih': f[1], 'musteri': f[2], 'tutar_tl': round(f[3] or 0),
                           'marj_yuzde': round(f[4], 1) if f[4] is not None else None} for f in faturalar]}

    # 6. iade orani: son 30 gun / onceki 6 ay
    def iade_orani(bas, bit):
        satis = _toplam(_q(measures=['net_tl'], direction='SATIS', date_from=bas, date_to=bit))
        iade = _toplam(_q(measures=['net_tl'], direction='TUMU', date_from=bas, date_to=bit,
                          filters={'direction': ['Satış iadesi']}))
        return round(100.0 * abs(iade) / satis, 2) if satis else 0
    s['iade_orani_yuzde'] = {'son_30_gun': iade_orani(g(29), b), 'onceki_6_ay': iade_orani(g(209), g(30))}

    # 7. alis / satis dengesi (stok sismesi)
    alis30 = _toplam(_q(measures=['net_tl'], direction='ALIS_NET', date_from=g(29), date_to=b))
    satis30 = _toplam(_q(measures=['net_tl'], date_from=g(29), date_to=b))
    s['son_30_gun_alis_satis'] = {'alis_tl': round(alis30), 'satis_tl': round(satis30),
                                  'alis_satis_orani': round(alis30 / satis30, 2) if satis30 else None}

    # 8. lisanslar ve abonelikler
    conn = get_db_connection()
    try:
        lis = conn.execute("""SELECT client_name, product_name, expiration_date, price FROM sales
                              WHERE status = 'PENDING' AND expiration_date BETWEEN ? AND ? ORDER BY price DESC LIMIT 10""",
                           (gercek_bugun.isoformat(), (gercek_bugun + timedelta(days=14)).isoformat())).fetchall()
        lis_say = conn.execute("""SELECT COUNT(*), SUM(price) FROM sales WHERE status = 'PENDING'
                                  AND expiration_date BETWEEN ? AND ?""", (gercek_bugun.isoformat(), (gercek_bugun + timedelta(days=14)).isoformat())).fetchone()
        abo = conn.execute("""SELECT client_name, product_name, days_since_last, avg_interval_days FROM subscriptions
                              WHERE status = 'AT_RISK' ORDER BY days_since_last LIMIT 10""").fetchall()
    finally:
        conn.close()
    s['14_gunde_dolacak_lisanslar'] = {
        'adet': lis_say[0], 'toplam_son_satis_tl': round(lis_say[1] or 0),
        'en_yuksek_tutarlilar': [{'musteri': r[0], 'urun': r[1], 'bitis': r[2], 'tutar_tl': round(r[3] or 0)} for r in lis]}
    s['riskli_abonelikler'] = [{'musteri': r[0], 'urun': r[1], 'son_faturadan_beri_gun': r[2],
                                'normal_aralik_gun': round(r[3] or 0)} for r in abo]
    return s


# ------------------------------------------------------------------ denetim
def hazir_mi(ayarlar=None):
    d = yapay_zeka.durum()
    return bool(d.get('acik'))


def _son_basliklar(gun=7):
    conn = get_db_connection()
    try:
        _tablo(conn)
        return [r[0] for r in conn.execute("SELECT baslik FROM asistan_gunlugu WHERE zaman >= ? AND kaynak = 'denetim'",
                                           ((datetime.now() - timedelta(days=gun)).isoformat(timespec='seconds'),))]
    finally:
        conn.close()


def _duz(x):
    """Model kurala ragmen **kalin** yazarsa isaretleri kaldirir."""
    return re.sub(r'\*\*(.+?)\*\*', r'\1', str(x or '')).strip()


def _json_ayikla(metin):
    m = re.search(r'\{.*\}', metin or '', re.S)
    if not m:
        raise ValueError('JSON yok')
    veri = json.loads(m.group(0))
    out = []
    for b in veri.get('bulgular') or []:
        onem = b.get('onem') if b.get('onem') in ('acil', 'onemli', 'bilgi') else 'bilgi'
        baslik, metin_ = _duz(b.get('baslik')), _duz(b.get('metin'))
        if baslik and metin_:
            out.append({'onem': onem, 'baslik': baslik, 'metin': metin_})
    return out


def denetle(neden='elle'):
    """Bir denetim turu. Doner: {'success', 'message', 'bulgular': [...]}"""
    if not _KILIT.acquire(blocking=False):
        return {'success': False, 'message': 'Bir denetim zaten çalışıyor.'}
    try:
        ayarlar = get_settings()
        if not hazir_mi(ayarlar):
            return {'success': False, 'message': 'Yapay zekâ kapalı ya da anahtar eksik (Ayarlar > Yapay zekâ).'}
        olcum = sinyaller()
        gorev = ('Bugünkü denetim ölçümleri (JSON, program hesapladı):\n' + json.dumps(olcum, ensure_ascii=False) +
                 '\n\nSon 7 günde zaten bildirilen başlıklar (tekrar etme, ancak durum belirgin kötüleştiyse yeniden yaz):\n- ' +
                 '\n- '.join(_son_basliklar() or ['(yok)']) +
                 f'\n\nDenetim nedeni: {neden}. Gerekirse araçlarla doğrula ya da derinleştir; sonra yalnızca JSON döndür.')
        try:
            sonuc = yapay_zeka.gorev(gorev, ROL, ayarlar)
            bulgular = _json_ayikla(sonuc['yanit'])
        except yapay_zeka.YapayZekaHatasi as e:
            _kaydet('bilgi', 'Denetim yapılamadı', str(e), kaynak='hata')
            return {'success': False, 'message': str(e)}
        except (ValueError, json.JSONDecodeError):
            _kaydet('bilgi', 'Denetim yanıtı okunamadı', 'Model beklenen biçimde yanıt vermedi; bir sonraki senkronda yeniden denenecek.',
                    kaynak='hata')
            return {'success': False, 'message': 'Model beklenen biçimde yanıt vermedi.'}

        kayitlar = []
        for b in bulgular:
            kimlik = _kaydet(b['onem'], b['baslik'], b['metin'], mail='' if b['onem'] == 'acil' else 'ozette')
            kayitlar.append({**b, 'id': kimlik})
        for b in kayitlar:
            if b['onem'] == 'acil':
                _acil_gonder(b, ayarlar)
        mesaj = f"Denetim tamamlandı: {len(kayitlar)} bulgu" + (
            f" ({sum(1 for b in kayitlar if b['onem'] == 'acil')} acil)." if kayitlar else '; dikkat gerektiren bir şey yok.')
        return {'success': True, 'message': mesaj, 'bulgular': kayitlar}
    finally:
        _KILIT.release()


def arka_planda_denetle(neden='senkron'):
    """Senkron sonrasi: ayar aciksa ve yapay zeka hazirsa denetimi arka planda baslatir."""
    try:
        if (get_settings().get('ai_watch') or 'ON') == 'OFF' or not hazir_mi():
            return False
    except Exception:
        return False
    threading.Thread(target=lambda: _guvenli(denetle, neden), daemon=True).start()
    return True


def _guvenli(f, *a):
    try:
        f(*a)
    except Exception as e:
        print(f'[Denetçi] {e}')


# ------------------------------------------------------------------ e-posta
def _alicilar(ayarlar):
    return [e.strip() for e in (ayarlar.get('internal_recipients') or '').split(',') if e.strip()]


def _gonder(ayarlar, konu, govde_html):
    import mailer
    alicilar = _alicilar(ayarlar)
    if not alicilar:
        return False, 'iç alıcı tanımlı değil'
    ok, mesaj = mailer.smtp_gonder(ayarlar, alicilar, konu, govde_html)
    if ok:
        conn = get_db_connection()
        try:
            mailer._gonderim_kaydet(conn.cursor(), konu, govde_html, alicilar, 'İç ekip', 'ASISTAN')
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
    return ok, mesaj


def _sablon(baslik, bulgular, ayarlar):
    renk = {'acil': '#c2410c', 'onemli': '#b45309', 'bilgi': '#0f8f82'}
    ad = {'acil': 'Acil', 'onemli': 'Önemli', 'bilgi': 'Bilgi'}
    url = (ayarlar.get('app_public_url') or '').rstrip('/')
    parcalar = ''.join(
        f"""<div style="border-left:3px solid {renk[b['onem']]};padding:6px 12px;margin:0 0 14px">
              <div style="font-size:12px;color:{renk[b['onem']]};font-weight:600">{ad[b['onem']]}</div>
              <div style="font-size:15px;font-weight:600;margin:2px 0 4px">{html.escape(b['baslik'])}</div>
              <div style="font-size:14px;line-height:1.5;color:#33403e;white-space:pre-wrap">{html.escape(b['metin'])}</div></div>"""
        for b in bulgular)
    dugme = (f'<p><a href="{html.escape(url)}/#/asistan" style="display:inline-block;background:#1fc8b6;color:#0b0f0e;'
             f'padding:8px 14px;text-decoration:none;border-radius:3px;font-weight:600">Asistan günlüğünü aç</a></p>') if url else ''
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:640px;color:#0b0f0e">
      <div style="font-size:13px;color:#5b6866">Tailglass Analytics · Asistan</div>
      <h2 style="font-size:19px;margin:6px 0 16px">{html.escape(baslik)}</h2>{parcalar}{dugme}
      <p style="font-size:12px;color:#7a8886">Bu e-postayı Tailglass'ın yapay zekâ denetçisi, senkronla gelen veriye bakarak hazırladı.
      Rakamlar programın hesapladığı değerlerdir; kararlarınızı vermeden önce uygulamada doğrulayın.</p></div>"""


def _bugun_gonderilen_acil():
    conn = get_db_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM asistan_gunlugu WHERE onem = 'acil' AND mail = 'gonderildi' AND zaman >= ?",
                            (date.today().isoformat(),)).fetchone()[0]
    finally:
        conn.close()


def _acil_gonder(b, ayarlar):
    try:
        sinir = int(ayarlar.get('ai_urgent_limit') or 3)
    except ValueError:
        sinir = 3
    if _bugun_gonderilen_acil() >= sinir:
        _mail_durumu(b['id'], 'ozette')       # gunluk sinir doldu: aksam ozetine
        return
    ok, mesaj = _gonder(ayarlar, f"Acil: {b['baslik']}", _sablon(b['baslik'], [b], ayarlar))
    _mail_durumu(b['id'], 'gonderildi' if ok else f'gonderilemedi: {mesaj}'[:200])


def gunluk_ozet_gonder():
    """Ozete bekleyen bulgulari tek mailde gonderir. Doner: {'success', 'message'}"""
    ayarlar = get_settings()
    conn = get_db_connection()
    try:
        _tablo(conn)
        rows = [dict(r) for r in conn.execute("""SELECT * FROM asistan_gunlugu WHERE mail = 'ozette' OR mail LIKE 'gonderilemedi%'
                                                 ORDER BY CASE onem WHEN 'acil' THEN 0 WHEN 'onemli' THEN 1 ELSE 2 END, id""")]
    finally:
        conn.close()
    if not rows:
        return {'success': True, 'message': 'Özette gönderilecek yeni bulgu yok.'}
    ok, mesaj = _gonder(ayarlar, f"Tailglass günlük özet — {len(rows)} bulgu ({date.today().strftime('%d.%m.%Y')})",
                        _sablon('Günün özeti', rows, ayarlar))
    for r in rows:
        _mail_durumu(r['id'], 'ozet_gonderildi' if ok else f'gonderilemedi: {mesaj}'[:200], ozet=ok)
    return {'success': ok, 'message': 'Günlük özet gönderildi.' if ok else f'Özet gönderilemedi: {mesaj}'}


def ozet_dongusu(kontrol_sn=60):
    """Arka plan: her gun ai_digest_hour saatinde bir kez gunluk ozet."""
    import time
    gonderilen = set()
    while True:
        try:
            ayarlar = get_settings()
            saat = int(ayarlar.get('ai_digest_hour') or 18)
            simdi = datetime.now()
            if (ayarlar.get('ai_watch') or 'ON') != 'OFF' and simdi.hour == saat and simdi.date() not in gonderilen:
                gonderilen.add(simdi.date())
                print(f"[Denetçi] {gunluk_ozet_gonder()['message']}")
        except Exception as e:
            print(f'[Denetçi özet] {e}')
        time.sleep(kontrol_sn)
