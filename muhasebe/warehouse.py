"""Logo -> yerel veri ambari senkronu.

Akis:
    1. Kartlar (urun, cari, temsilci, marka) ve stok hareket satirlari
       Logo'dan (ya da demo veritabanindan) okunur.
    2. Satirlar `data_start_date` ayarindan itibaren (bos ise TUM gecmis)
       wh_lines tablosuna yazilir — tek transaction, yarim kalirsa eski veri
       aynen durur.
    3. Urunler siniflandirilir (marka/kategori/tur/gelir tipi).
    4. FIFO: her satis satiri icin hangi alistan karsilandigi hesaplanir ->
       tahmini maliyet, kar ve "depoda bekleme suresi".

Iptal edilen faturalar ambarda kalir (cancelled=1) ama hicbir analize girmez.
"""

import time
from collections import defaultdict, deque
from datetime import datetime

from database import get_db_connection, get_settings
from logo_source import tarih_str
from kaynaklar import kaynak_ac
import siniflandirma

# Fatura TRCODE -> yon. Fatura disi stok fisleri (sayim, devir, fire,
# ambar transferi) DIGER olur: stoku etkiler ama alis/satis sayilmaz.
SATIS_TR = {7, 8, 9}
SATIS_IADE_TR = {2, 3}
ALIS_TR = {1, 4}
ALIS_IADE_TR = {6}

GIRIS_IO = {1, 2}
CIKIS_IO = {3, 4}

HIZMET_REF_OFSETI = -1  # hizmet kartlari (SRVCARD) urunlerle carpismasin diye negatif ref


def yon_bul(trcode, faturali):
    if not faturali:
        return 'DIGER'
    if trcode in SATIS_TR:
        return 'SATIS'
    if trcode in SATIS_IADE_TR:
        return 'SATIS_IADE'
    if trcode in ALIS_TR:
        return 'ALIS'
    if trcode in ALIS_IADE_TR:
        return 'ALIS_IADE'
    return 'DIGER'


def _f(x):
    try:
        return float(x) if x is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _metin(x):
    t = (x or '').strip() if isinstance(x, str) else (str(x).strip() if x is not None else '')
    return '' if t in ('-', '.', '_') else t


# ------------------------------------------------------------------ senkron
def senkronize_et(ayarlar=None, ilerleme=None):
    """Logo'dan ambara tam senkron. Doner: ozet dict."""
    ayarlar = ayarlar or get_settings()
    bas = (ayarlar.get('data_start_date') or '').strip() or None
    log = ilerleme or (lambda m: None)
    t0 = time.time()
    baslangic_zamani = datetime.now().isoformat(timespec='seconds')

    conn = get_db_connection()
    satir_sayisi = 0
    # Logo okunurken satirlar parca parca yerel veritabanina yazilir: gercek
    # Logo'da 200 bin+ satir tek seferde bellege alinmaz. Hepsi tek
    # transaction'da — yarida kalirsa eski veri aynen durur.
    try:
        with kaynak_ac(ayarlar) as k:
            kaynak = k.mod
            log('Kartlar okunuyor')
            markalar = k.markalar()
            urunler = list(k.urunler())
            hizmetler = k.hizmetler()
            cariler = list(k.cariler())
            temsilciler = list(k.temsilciler())
            kurlar = k.doviz_kurlari()
            kur_gunleri = sorted(kurlar)

            def gunluk_kur(gun):
                # Raporlama kuru bos gelen satirlar icin: en yakin onceki gunun kuru
                if not kur_gunleri:
                    return None
                import bisect
                i = bisect.bisect_right(kur_gunleri, gun) - 1
                return kurlar[kur_gunleri[i]] if i >= 0 else kurlar[kur_gunleri[0]]

            cur = conn.cursor()
            cur.execute('BEGIN')
            cur.execute('DELETE FROM wh_clients')
            cur.executemany('INSERT INTO wh_clients VALUES (?,?,?,?,?,?,?)', [
                (c['ref'], _metin(c['code']), _metin(c['name']) or 'Bilinmeyen Cari', c.get('cardtype'),
                 _metin(c.get('email')), _metin(c.get('phone')), _metin(c.get('city')).upper())
                for c in cariler])
            cur.execute('DELETE FROM wh_salesmen')
            cur.executemany('INSERT INTO wh_salesmen VALUES (?,?,?)', [
                (t['ref'], _metin(t['code']), _metin(t['name'])) for t in temsilciler])

            ham_urunler = [{
                'item_ref': u['ref'], 'code': _metin(u['code']), 'name': _metin(u['name']) or f"Ürün #{u['ref']}",
                'logo_brand': markalar.get(u.get('markref') or 0, ''), 'logo_group': _metin(u.get('grp')),
            } for u in urunler] + [{
                'item_ref': HIZMET_REF_OFSETI * h['ref'], 'code': _metin(h['code']),
                'name': _metin(h['name']) or f"Hizmet #{h['ref']}", 'logo_brand': '', 'logo_group': 'HIZMET',
            } for h in hizmetler]

            # Baslangic tarihi degistiyse (ileri alindiysa) eski satirlar da gitmeli:
            # ambar her senkronda tamamen yenilenir.
            cur.execute('DELETE FROM wh_lines')
            log('Hareket satırları okunuyor')
            parca = []
            for s in k.satirlar(bas):
                parca.append(_satir_kaydi(s, gunluk_kur))
                if len(parca) >= 5000:
                    _satirlari_yaz(cur, parca)
                    satir_sayisi += len(parca)
                    parca = []
                    log(f'{satir_sayisi:,} satır aktarıldı')
            _satirlari_yaz(cur, parca)
            satir_sayisi += len(parca)

            log('Ürünler sınıflandırılıyor')
            _urunleri_yaz(cur, ham_urunler)
            cur.execute('COMMIT')
    except Exception:
        conn.rollback()
        conn.close()
        raise

    log('Maliyetler hesaplanıyor (FIFO)')
    fifo_hesapla(conn)
    ozet = {
        'source': kaynak, 'lines': satir_sayisi, 'items': len(urunler) + len(hizmetler), 'clients': len(cariler),
        'seconds': round(time.time() - t0, 1), 'start_date': bas or 'tümü',
    }
    conn.execute('''INSERT INTO sync_log (started_at, finished_at, source, ok, lines, items, clients, message)
                    VALUES (?,?,?,?,?,?,?,?)''',
                 (baslangic_zamani, datetime.now().isoformat(timespec='seconds'), kaynak, 1, ozet['lines'],
                  ozet['items'], ozet['clients'], ''))
    conn.commit()
    conn.close()
    return ozet


def _satir_kaydi(s, gunluk_kur):
    tarih = tarih_str(s['date'])
    linetype = int(s['linetype'] or 0)
    inv_ref = int(s['inv_ref'] or 0)
    iptal = 1 if (s.get('line_cancelled') or s.get('inv_cancelled')) else 0
    yon = yon_bul(int(s['trcode'] or 0), inv_ref > 0) if linetype in (0, 4) else 'DIGER'
    item_ref = int(s['item_ref'] or 0)
    if linetype == 4 and item_ref:
        item_ref = HIZMET_REF_OFSETI * item_ref
    elif linetype != 0:
        item_ref = 0                     # indirim, sabit kiymet vb. — urun degil
    net = _f(s['net']) if s['net'] is not None else _f(s['gross'])
    kur = _f(s['rate'])
    if kur <= 0:
        kur = gunluk_kur(tarih) or 0
    client_ref = int(s['client_ref'] or s.get('inv_client') or 0)
    salesman = int(s['salesman_ref'] or s.get('inv_salesman') or 0)
    return (int(s['line_ref']), s['period'], inv_ref, _metin(s.get('fiche_no')), tarih, int(s['trcode'] or 0),
            int(s['iocode'] or 0), linetype, yon, client_ref, item_ref, salesman,
            _f(s['qty']), _f(s['price']), _f(s['gross']), net, kur or None, (net / kur) if kur else None, iptal)


def _satirlari_yaz(cur, kayitlar):
    if kayitlar:
        cur.executemany('''
            INSERT OR REPLACE INTO wh_lines (line_ref, period, inv_ref, fiche_no, date, trcode, iocode, linetype,
                direction, client_ref, item_ref, salesman_ref, qty, price_tl, gross_tl, net_tl, rate, net_usd,
                cancelled)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', kayitlar)


def _urunleri_yaz(cur, ham_urunler):
    kurallar = [dict(r) for r in cur.execute('SELECT field, pattern, value FROM class_rules ORDER BY id')]
    ilk_kelime_sayisi = defaultdict(int)
    for u in ham_urunler:
        ik = siniflandirma.ilk_kelime(u['name'])
        if ik:
            ilk_kelime_sayisi[ik] += 1
    cur.execute('DELETE FROM wh_items')
    cur.executemany('''INSERT INTO wh_items (item_ref, code, name, logo_brand, logo_group, brand, brand_src,
                                             category, category_src, kind, revenue_type, duration_months)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', [
        (s['item_ref'], s['code'], s['name'], s['logo_brand'], s['logo_group'], s['brand'], s['brand_src'],
         s['category'], s['category_src'], s['kind'], s['revenue_type'], s['duration_months'])
        for s in (siniflandirma.siniflandir(u, kurallar, ilk_kelime_sayisi) for u in ham_urunler)])


def yeniden_siniflandir():
    """Kurallar degisince Logo'ya gitmeden urunleri yeniden siniflandirir."""
    conn = get_db_connection()
    cur = conn.cursor()
    ham = [{'item_ref': r['item_ref'], 'code': r['code'], 'name': r['name'],
            'logo_brand': r['logo_brand'], 'logo_group': r['logo_group']}
           for r in cur.execute('SELECT item_ref, code, name, logo_brand, logo_group FROM wh_items')]
    _urunleri_yaz(cur, ham)
    conn.commit()
    conn.close()
    return len(ham)


# ------------------------------------------------------------------ FIFO
def fifo_hesapla(conn=None):
    """Her satis satirina FIFO maliyeti ve karsiladigi ilk alisin tarihini yazar.

    Tahmindir ve oyle etiketlenir: Logo seri/lot takibi yapmiyorsa hangi
    fiziksel urunun satildigini bilemeyiz; FIFO muhasebedeki standart
    varsayim. Ambarin baslangic tarihinden once alinmis stok bilinmedigi
    icin o satislarin maliyeti "eksik" (cost_complete=0) isaretlenir.
    """
    kendi = conn is None
    conn = conn or get_db_connection()
    rows = conn.execute('''
        SELECT period, line_ref, item_ref, date, iocode, direction, qty, net_tl, net_usd
        FROM wh_lines
        WHERE cancelled = 0 AND item_ref > 0 AND linetype = 0 AND iocode IN (1,2,3,4) AND qty > 0
        ORDER BY item_ref, date, CASE WHEN iocode IN (1,2) THEN 0 ELSE 1 END, line_ref''').fetchall()

    guncelle = []
    lotlar = deque()
    son_item = None
    son_maliyet = (0.0, 0.0)
    for r in rows:
        if r['item_ref'] != son_item:
            lotlar = deque()
            son_item = r['item_ref']
            son_maliyet = (0.0, 0.0)
        qty = r['qty']
        if r['iocode'] in GIRIS_IO:
            if r['direction'] == 'ALIS' and qty:
                birim = (r['net_tl'] / qty, (r['net_usd'] or 0) / qty)
                son_maliyet = birim
            else:
                birim = son_maliyet          # iade/devir/sayim girisi: bilinen son maliyet
            lotlar.append([qty, birim[0], birim[1], r['date']])
            continue
        # cikis
        kalan, tl, usd, ilk_tarih = qty, 0.0, 0.0, None
        while kalan > 1e-9 and lotlar:
            lot = lotlar[0]
            al = min(kalan, lot[0])
            tl += al * lot[1]
            usd += al * lot[2]
            ilk_tarih = ilk_tarih or lot[3]
            lot[0] -= al
            kalan -= al
            if lot[0] <= 1e-9:
                lotlar.popleft()
        if r['direction'] == 'SATIS':
            tamam = 1 if kalan <= 1e-9 else 0
            guncelle.append((round(tl, 2) if ilk_tarih else None, round(usd, 4) if ilk_tarih else None,
                             ilk_tarih, tamam, r['period'], r['line_ref']))

    conn.execute('UPDATE wh_lines SET cost_tl = NULL, cost_usd = NULL, cost_date = NULL, cost_complete = NULL')
    conn.executemany('''UPDATE wh_lines SET cost_tl = ?, cost_usd = ?, cost_date = ?, cost_complete = ?
                        WHERE period = ? AND line_ref = ?''', guncelle)
    conn.commit()
    if kendi:
        conn.close()
    return len(guncelle)


if __name__ == '__main__':
    import json
    print(json.dumps(senkronize_et(ilerleme=print), ensure_ascii=False, indent=2))
