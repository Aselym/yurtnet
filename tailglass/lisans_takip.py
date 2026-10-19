"""Lisans ve abonelik takibi — veri ambarindan turetilir.

Eskiden logo_sync.py bunlar icin Logo'ya ayri ayri sorgu atiyordu; artik
tum satirlar zaten wh_lines'ta oldugu icin Logo'ya ikinci kez gidilmez.

  1. Sureli lisanslar (sales tablosu): kullanici durumu tasir (yenileme
     karari, elle girilen sure, gonderilen hatirlatma). Bu yuzden yalnizca
     YENI satirlar eklenir, mevcutlara dokunulmaz. logo_ref bicimi eskisiyle
     ayni ("FICHENO#STLINE_REF") — canli veritabanindaki 362 kayit korunur.
  2. Abonelikler (subscriptions): tamamen turetilmis veri, her senkronda
     yeniden hesaplanir. Bagli firmalar (client_groups) tek musteri sayilir.
  3. Yenileme adaylari: suresi dolan lisansin yerine satilmis yeni lisans.
"""

import re
from datetime import datetime

from database import (get_db_connection, get_settings, calculate_dates, sure_dolmuslari_isaretle,
                      setting_float)
import siniflandirma


def _sure_tipi(ay):
    return {12: '1_YEAR', 24: '2_YEARS', 36: '3_YEARS', 60: '5_YEARS'}.get(ay, 'CUSTOM')


def lisanslari_turet(ayarlar=None):
    """Doner: (eklenen, sure_bekleyen, atlanan)"""
    ayarlar = ayarlar or get_settings()
    en_eski_bitis = ayarlar.get('license_min_expiry') or '1900-01-01'
    conn = get_db_connection()
    cur = conn.cursor()
    mevcut = {r[0] for r in cur.execute('SELECT logo_ref FROM sales WHERE logo_ref IS NOT NULL')}
    satirlar = cur.execute('''
        SELECT l.line_ref, l.fiche_no, l.date, l.net_tl, i.name AS urun, i.code AS urun_kod, i.duration_months,
               c.name AS cari, c.code AS cari_kod, c.email, c.phone, c.city, s.name AS temsilci
        FROM wh_lines l
        JOIN wh_items i ON i.item_ref = l.item_ref
        LEFT JOIN wh_clients c ON c.client_ref = l.client_ref
        LEFT JOIN wh_salesmen s ON s.salesman_ref = l.salesman_ref
        WHERE l.direction = 'SATIS' AND l.cancelled = 0 AND i.kind = 'lisans'
        ORDER BY l.date DESC''').fetchall()

    eklenen = sure_bekleyen = atlanan = 0
    for r in satirlar:
        logo_ref = f"{r['fiche_no']}#{r['line_ref']}"
        if logo_ref in mevcut:
            atlanan += 1
            continue
        ay = r['duration_months']
        if ay:
            bitis = calculate_dates(r['date'], ay)
            if bitis < en_eski_bitis:
                atlanan += 1
                continue
            durum = 'PENDING'
        else:
            if calculate_dates(r['date'], 36) < en_eski_bitis:
                atlanan += 1
                continue
            ay, bitis, durum = 0, r['date'], 'NEEDS_DURATION'
            sure_bekleyen += 1
        cur.execute('''
            INSERT INTO sales (product_name, client_name, client_email, sales_rep, license_key, sale_date,
                               duration_type, duration_months, expiration_date, reminder_type, status, notes,
                               logo_ref, source, price, client_phone, client_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'STAGED', ?, ?, ?, 'LOGO', ?, ?, ?)''',
            (r['urun'], r['cari'] or 'Bilinmeyen Müşteri', r['email'] or '', r['temsilci'] or '',
             r['urun_kod'] or '', r['date'], _sure_tipi(ay), ay, bitis, durum,
             f"Logo faturası {r['fiche_no']} (cari {r['cari_kod'] or '-'})", logo_ref, r['net_tl'],
             r['phone'] or '', r['city'] or ''))
        mevcut.add(logo_ref)
        eklenen += 1
    conn.commit()
    conn.close()
    sure_dolmuslari_isaretle()
    return eklenen, sure_bekleyen, atlanan


def abonelikleri_turet(ayarlar=None):
    """Doner: (yazilan, riskli)"""
    ayarlar = ayarlar or get_settings()
    min_fatura = int(setting_float(ayarlar, 'sub_min_invoices', 4))
    max_aralik = setting_float(ayarlar, 'sub_max_interval_days', 60)
    risk_kat = setting_float(ayarlar, 'sub_risk_factor', 2.0)

    conn = get_db_connection()
    cur = conn.cursor()
    gruplar = {r['client_name']: r['group_name'] for r in cur.execute('SELECT * FROM client_groups')}
    satirlar = cur.execute('''
        SELECT c.name AS cari, c.email, c.phone, c.city, i.name AS urun, l.date
        FROM wh_lines l
        JOIN wh_items i ON i.item_ref = l.item_ref
        LEFT JOIN wh_clients c ON c.client_ref = l.client_ref
        WHERE l.direction = 'SATIS' AND l.cancelled = 0 AND i.kind = 'abonelik'
        ORDER BY l.date''').fetchall()

    # (musteri ya da firma grubu, urun) -> fatura tarihleri
    toplam = {}
    for r in satirlar:
        cari = r['cari'] or 'Bilinmeyen Müşteri'
        anahtar = (gruplar.get(cari, cari), r['urun'])
        k = toplam.setdefault(anahtar, {'tarihler': [], 'email': r['email'], 'phone': r['phone'],
                                        'city': r['city'], 'firmalar': set()})
        k['tarihler'].append(r['date'])
        k['firmalar'].add(cari)

    bugun = datetime.now().date()
    cur.execute('DELETE FROM subscriptions')
    yazilan = riskli = 0
    for (musteri, urun), k in toplam.items():
        if siniflandirma.kalici_lisans_mi(urun):
            continue
        tarihler = sorted(set(k['tarihler']))
        adet = len(tarihler)
        ilk = datetime.strptime(tarihler[0], '%Y-%m-%d').date()
        son = datetime.strptime(tarihler[-1], '%Y-%m-%d').date()
        gun_farki = (son - ilk).days
        ortalama = (gun_farki / (adet - 1)) if adet > 1 and gun_farki > 0 else 30.0
        gecen = (bugun - son).days
        if adet < min_fatura or ortalama > max_aralik:
            continue
        if gecen > ortalama * risk_kat * 2:
            durum = 'LOST'
        elif gecen > ortalama * risk_kat:
            durum = 'AT_RISK'
            riskli += 1
        else:
            durum = 'ACTIVE'
        cur.execute('''
            INSERT INTO subscriptions (client_name, client_email, product_name, first_invoice_date,
                last_invoice_date, invoice_count, avg_interval_days, days_since_last, status, source,
                updated_at, client_phone, client_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOGO', CURRENT_TIMESTAMP, ?, ?)''',
            (musteri, k['email'] or '', urun, ilk.isoformat(), son.isoformat(), adet, round(ortalama, 1),
             gecen, durum, k['phone'] or '', k['city'] or ''))
        yazilan += 1
    conn.commit()
    conn.close()
    return yazilan, riskli


# ---------------------------------------------------------------- yenileme
YENILEME_KATEGORILERI = [
    ('endpoint', ('EPDR', 'ESB', 'ENDPOINT', 'EPP', 'PATCH MANAGEMENT', 'WGPTCH')),
    ('log5651', ('5651', 'PLOG', 'SIGNLOGGER', 'HOTSPOT')),
    ('mfa', ('AUTHPOINT', 'WGATH')),
    ('backup', ('VEEAM', 'BACKUP')),
    ('dns', ('DNSWATCH', 'WGDNS')),
]
FIREWALL_IPUCU = ('WATCHGUARD', 'WATCGUARD', 'FIREBOX', 'FORTIGATE')
_MODEL_DESEN = re.compile(r'WG([TMV][A-Z]*\d+|ME\d*)')


def yenileme_kategorisi(urun_adi):
    m = (urun_adi or '').upper()
    for ad, kelimeler in YENILEME_KATEGORILERI:
        if any(k in m for k in kelimeler):
            return ad
    if any(k in m for k in FIREWALL_IPUCU):
        model = _MODEL_DESEN.search(m.replace(' ', ''))
        if model:
            taban = re.match(r'([A-Z]+)(\d{2,3})', model.group(1))
            if taban:
                return f'firewall:{taban.group(1)}{taban.group(2)[:2]}'
        return 'firewall:?'
    for kelimeler, ad_ in siniflandirma.MARKA_SOZLUGU:
        if any(k in m for k in kelimeler):
            return f'marka:{ad_}'
    return 'diger'


def yenileme_adaylari_bul():
    """Birebir ayni urun tekrar satildiysa otomatik RENEWED; sadece kategori
    eslesiyorsa SUSPECT (satis ekibi onaylar)."""
    conn = get_db_connection()
    cur = conn.cursor()
    kayitlar = [dict(r) for r in cur.execute('SELECT * FROM sales').fetchall()]
    for k in kayitlar:
        k['_kat'] = yenileme_kategorisi(k['product_name'])
        k['_urun_norm'] = (k['product_name'] or '').strip().upper()

    isaretlenen = 0
    for eski in kayitlar:
        if eski['status'] != 'EXPIRED' or eski.get('renewal_state') in ('CONFIRMED', 'REJECTED'):
            continue
        adaylar = [y for y in kayitlar
                   if y['id'] != eski['id'] and y['client_name'] == eski['client_name']
                   and y['_kat'] == eski['_kat'] and y['_kat'] != 'diger'
                   and (y['sale_date'] or '') > (eski['sale_date'] or '')]
        if not adaylar:
            continue
        birebir = [y for y in adaylar if y['_urun_norm'] == eski['_urun_norm']]
        if birebir:
            en_yeni = max(birebir, key=lambda x: x['sale_date'])
            cur.execute("UPDATE sales SET renewed_by = ?, renewal_state = 'CONFIRMED', status = 'RENEWED' "
                        "WHERE id = ?", (en_yeni['id'], eski['id']))
        else:
            en_yeni = max(adaylar, key=lambda x: x['sale_date'])
            cur.execute("UPDATE sales SET renewed_by = ?, renewal_state = 'SUSPECT' WHERE id = ?",
                        (en_yeni['id'], eski['id']))
        isaretlenen += 1
    conn.commit()
    conn.close()
    return isaretlenen
