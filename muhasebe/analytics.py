"""Analiz motoru: kullanici ne secerse o hesaplanir.

Hicbir rapor sabit degil. Her istek su parcalardan olusur:
    - donem (date_from/date_to)
    - yon (satis, alis; iadeler dusulsun mu)
    - filtreler (marka, kategori, musteri, firma grubu, temsilci, sehir,
      tur, gelir tipi, urun) + serbest metin arama
    - kirilimlar (satirlar) + istege bagli pivot kolonu
    - olculer (TL, USD, adet, maliyet, kar, marj, fatura/musteri sayisi...)
SQL yalnizca beyaz listedeki boyut/olcu ifadelerinden kurulur; kullanicidan
gelen degerler her zaman parametre olarak gecer.
"""

from datetime import date, timedelta

from database import get_db_connection

# ------------------------------------------------------------------ boyutlar
BOYUTLAR = {
    'day':          ("l.date", 'Gün'),
    'week':         ("strftime('%Y-H%W', l.date)", 'Hafta'),
    'month':        ("substr(l.date,1,7)", 'Ay'),
    'quarter':      ("substr(l.date,1,4)||'-Ç'||((CAST(substr(l.date,6,2) AS INTEGER)+2)/3)", 'Çeyrek'),
    'year':         ("substr(l.date,1,4)", 'Yıl'),
    'weekday':      ("CASE strftime('%w', l.date) WHEN '1' THEN '1 Pazartesi' WHEN '2' THEN '2 Salı' "
                     "WHEN '3' THEN '3 Çarşamba' WHEN '4' THEN '4 Perşembe' WHEN '5' THEN '5 Cuma' "
                     "WHEN '6' THEN '6 Cumartesi' ELSE '7 Pazar' END", 'Haftanın günü'),
    'client':       ("COALESCE(c.name, 'Bilinmeyen Cari')", 'Müşteri / Cari'),
    'client_group': ("COALESCE(g.group_name, c.name, 'Bilinmeyen Cari')", 'Firma grubu'),
    'city':         ("COALESCE(NULLIF(c.city,''), 'Belirsiz')", 'Şehir'),
    'brand':        ("COALESCE(i.brand, 'Markasız')", 'Marka'),
    'category':     ("COALESCE(i.category, 'Diğer')", 'Kategori'),
    'kind':         ("CASE i.kind WHEN 'lisans' THEN 'Süreli lisans' WHEN 'abonelik' THEN 'Abonelik' "
                     "WHEN 'kalici' THEN 'Kalıcı yazılım' ELSE 'Ürün' END", 'Ürün türü'),
    'revenue_type': ("COALESCE(i.revenue_type, 'Ürün')", 'Gelir tipi'),
    'item':         ("COALESCE(i.name, 'Bilinmeyen Ürün')", 'Ürün'),
    'item_code':    ("COALESCE(i.code, '')", 'Ürün kodu'),
    'salesman':     ("COALESCE(NULLIF(s.name,''), 'Atanmamış')", 'Temsilci'),
    'direction':    ("CASE l.direction WHEN 'SATIS' THEN 'Satış' WHEN 'ALIS' THEN 'Alış' "
                     "WHEN 'SATIS_IADE' THEN 'Satış iadesi' WHEN 'ALIS_IADE' THEN 'Alış iadesi' ELSE 'Diğer' END",
                     'Hareket'),
    'aging_bucket': ("CASE WHEN l.cost_date IS NULL THEN 'Bilinmiyor' "
                     "WHEN julianday(l.date)-julianday(l.cost_date) <= 7 THEN '0-7 gün' "
                     "WHEN julianday(l.date)-julianday(l.cost_date) <= 30 THEN '8-30 gün' "
                     "WHEN julianday(l.date)-julianday(l.cost_date) <= 90 THEN '31-90 gün' "
                     "WHEN julianday(l.date)-julianday(l.cost_date) <= 180 THEN '91-180 gün' "
                     "WHEN julianday(l.date)-julianday(l.cost_date) <= 365 THEN '181-365 gün' "
                     "ELSE '365+ gün' END", 'Depoda bekleme'),
}

# Filtrelenebilir boyutlar (IN listesi) — tarih boyutlari haric
FILTRE_BOYUTLARI = ['client', 'client_group', 'city', 'brand', 'category', 'kind', 'revenue_type', 'item',
                    'salesman', 'direction', 'year', 'month', 'aging_bucket']

# ------------------------------------------------------------------ olculer
ISARET = "(CASE WHEN l.direction IN ('SATIS_IADE','ALIS_IADE') THEN -1 ELSE 1 END)"
MALIYETLI = "(l.direction = 'SATIS' AND l.cost_complete = 1)"
OLCULER = {
    'net_tl':      (f"SUM({ISARET}*l.net_tl)", 'Tutar (TL)', 'tl'),
    'net_usd':     (f"SUM({ISARET}*l.net_usd)", 'Tutar (USD)', 'usd'),
    'qty':         (f"SUM({ISARET}*l.qty)", 'Adet', 'num'),
    'cost_tl':     (f"SUM(CASE WHEN {MALIYETLI} THEN l.cost_tl END)", 'Maliyet (TL, FIFO)', 'tl'),
    'cost_usd':    (f"SUM(CASE WHEN {MALIYETLI} THEN l.cost_usd END)", 'Maliyet (USD, FIFO)', 'usd'),
    'profit_tl':   (f"SUM(CASE WHEN {MALIYETLI} THEN l.net_tl - l.cost_tl END)", 'Brüt kâr (TL)', 'tl'),
    'profit_usd':  (f"SUM(CASE WHEN {MALIYETLI} THEN l.net_usd - l.cost_usd END)", 'Brüt kâr (USD)', 'usd'),
    'margin':      (f"100.0*SUM(CASE WHEN {MALIYETLI} THEN l.net_tl - l.cost_tl END)"
                    f"/NULLIF(SUM(CASE WHEN {MALIYETLI} THEN l.net_tl END),0)", 'Kâr marjı (%)', 'pct'),
    'margin_usd':  (f"100.0*SUM(CASE WHEN {MALIYETLI} THEN l.net_usd - l.cost_usd END)"
                    f"/NULLIF(SUM(CASE WHEN {MALIYETLI} THEN l.net_usd END),0)", 'Kâr marjı USD (%)', 'pct'),
    'lines':       ("COUNT(*)", 'Satır sayısı', 'num'),
    'invoices':    ("COUNT(DISTINCT l.inv_ref)", 'Fatura sayısı', 'num'),
    'clients':     ("COUNT(DISTINCT l.client_ref)", 'Müşteri sayısı', 'num'),
    'items':       ("COUNT(DISTINCT l.item_ref)", 'Ürün çeşidi', 'num'),
    'avg_price_tl': (f"SUM({ISARET}*l.net_tl)/NULLIF(SUM({ISARET}*l.qty),0)", 'Ort. birim fiyat (TL)', 'tl'),
    'avg_rate':    ("SUM(l.net_tl)/NULLIF(SUM(l.net_usd),0)", 'Ort. USD kuru', 'num'),
    'stock_age':   ("AVG(CASE WHEN l.cost_date IS NOT NULL THEN julianday(l.date)-julianday(l.cost_date) END)",
                    'Ort. depoda bekleme (gün)', 'num'),
}

YONLER = {
    'SATIS': ('SATIS',), 'ALIS': ('ALIS',),
    'SATIS_NET': ('SATIS', 'SATIS_IADE'), 'ALIS_NET': ('ALIS', 'ALIS_IADE'),
    'TUMU': ('SATIS', 'SATIS_IADE', 'ALIS', 'ALIS_IADE'),
}

JOINLER = """
    FROM wh_lines l
    LEFT JOIN wh_items i ON i.item_ref = l.item_ref
    LEFT JOIN wh_clients c ON c.client_ref = l.client_ref
    LEFT JOIN client_groups g ON g.client_name = c.name
    LEFT JOIN wh_salesmen s ON s.salesman_ref = l.salesman_ref
"""


class GecersizIstek(ValueError):
    pass


def _tarih(x, varsayilan):
    if not x:
        return varsayilan
    try:
        return date.fromisoformat(str(x)[:10]).isoformat()
    except ValueError:
        raise GecersizIstek(f'Geçersiz tarih: {x}')


def kosullar(istek):
    """WHERE parcasi + parametreler. Butun analiz uclari bunu paylasir."""
    where = ["l.cancelled = 0", "l.item_ref <> 0"]
    params = []
    bas = _tarih(istek.get('date_from'), '1900-01-01')
    bit = _tarih(istek.get('date_to'), '2999-12-31')
    where += ["l.date >= ?", "l.date <= ?"]
    params += [bas, bit]

    yon = istek.get('direction') or 'SATIS_NET'
    if yon not in YONLER:
        raise GecersizIstek(f'Geçersiz yön: {yon}')
    where.append(f"l.direction IN ({','.join('?' * len(YONLER[yon]))})")
    params += list(YONLER[yon])

    for boyut, degerler in (istek.get('filters') or {}).items():
        if boyut not in BOYUTLAR:
            raise GecersizIstek(f'Geçersiz filtre: {boyut}')
        if not degerler:
            continue
        haric = False
        if isinstance(degerler, dict):          # {"not": true, "values": [...]}
            haric = bool(degerler.get('not'))
            degerler = degerler.get('values') or []
        if not degerler:
            continue
        ifade = BOYUTLAR[boyut][0]
        where.append(f"{ifade} {'NOT ' if haric else ''}IN ({','.join('?' * len(degerler))})")
        params += [str(v) for v in degerler]

    arama = (istek.get('search') or '').strip()
    if arama:
        for kelime in arama.split():
            where.append("(i.name LIKE ? OR i.code LIKE ? OR c.name LIKE ? OR l.fiche_no LIKE ?)")
            params += [f'%{kelime}%'] * 4

    for alan, isaret in (('min_net_tl', '>='), ('max_net_tl', '<=')):
        if istek.get(alan) not in (None, ''):
            where.append(f"l.net_tl {isaret} ?")
            params.append(float(istek[alan]))
    return ' AND '.join(where), params


def _olcu_listesi(istek, varsayilan=('net_tl', 'net_usd', 'qty')):
    olculer = istek.get('measures') or list(varsayilan)
    for o in olculer:
        if o not in OLCULER:
            raise GecersizIstek(f'Geçersiz ölçü: {o}')
    return olculer


def sorgu(istek):
    """Gruplu analiz + istege bagli pivot."""
    gruplar = istek.get('group_by') or []
    if len(gruplar) > 4:
        raise GecersizIstek('En fazla 4 kırılım seçilebilir.')
    for gb in gruplar:
        if gb not in BOYUTLAR:
            raise GecersizIstek(f'Geçersiz kırılım: {gb}')
    pivot = istek.get('pivot_by')
    if pivot and pivot not in BOYUTLAR:
        raise GecersizIstek(f'Geçersiz pivot: {pivot}')
    olculer = _olcu_listesi(istek)
    where, params = kosullar(istek)

    secilen = [f"{BOYUTLAR[g][0]} AS d{n}" for n, g in enumerate(gruplar)]
    if pivot:
        secilen.append(f"{BOYUTLAR[pivot][0]} AS p")
    secilen += [f"{OLCULER[o][0]} AS m_{o}" for o in olculer]
    grup_ifade = [f"d{n}" for n in range(len(gruplar))] + (['p'] if pivot else [])
    sql = f"SELECT {', '.join(secilen)} {JOINLER} WHERE {where}"
    if grup_ifade:
        sql += f" GROUP BY {', '.join(grup_ifade)}"

    conn = get_db_connection()
    try:
        satirlar = [dict(r) for r in conn.execute(sql, params).fetchall()]
        toplam_sql = f"SELECT {', '.join(f'{OLCULER[o][0]} AS m_{o}' for o in olculer)} {JOINLER} WHERE {where}"
        toplam = dict(conn.execute(toplam_sql, params).fetchone())
    finally:
        conn.close()

    kolonlar = ([{'key': f'd{n}', 'label': BOYUTLAR[g][1], 'type': 'dim', 'dim': g} for n, g in enumerate(gruplar)] +
                [{'key': f'm_{o}', 'label': OLCULER[o][1], 'type': OLCULER[o][2], 'measure': o} for o in olculer])

    if pivot:
        return _pivotla(satirlar, gruplar, olculer, kolonlar, toplam, istek)

    sirala = istek.get('sort') or {}
    anahtar = sirala.get('key') or (f'm_{olculer[0]}' if olculer else (f'd0' if gruplar else None))
    if anahtar:
        tersine = sirala.get('desc', not anahtar.startswith('d'))
        satirlar.sort(key=lambda r: (r.get(anahtar) is None, r.get(anahtar) if r.get(anahtar) is not None else 0),
                      reverse=bool(tersine))
        if tersine:   # None'lar sona
            satirlar.sort(key=lambda r: r.get(anahtar) is None)
    toplam_satir = len(satirlar)
    limit = int(istek.get('limit') or 0)
    if limit > 0:
        satirlar = satirlar[:limit]
    return {'columns': kolonlar, 'rows': satirlar, 'totals': toplam, 'row_count': toplam_satir}


def _pivotla(satirlar, gruplar, olculer, kolonlar, toplam, istek):
    olcu = olculer[0]
    mk = f'm_{olcu}'
    pivot_toplam = {}
    for r in satirlar:
        pivot_toplam[r['p']] = pivot_toplam.get(r['p'], 0) + (r[mk] or 0)
    # Zaman pivotu kronolojik, diger pivotlar buyukten kucuge
    zaman = istek.get('pivot_by') in ('day', 'week', 'month', 'quarter', 'year', 'weekday')
    degerler = sorted(pivot_toplam, key=lambda v: (v is None, v)) if zaman else \
        sorted(pivot_toplam, key=lambda v: -(pivot_toplam[v] or 0))
    max_kolon = int(istek.get('pivot_limit') or 24)
    digerleri = set()
    if len(degerler) > max_kolon:
        digerleri = set(degerler[max_kolon - 1:]) if not zaman else set(degerler[:-max_kolon + 1])
        degerler = [v for v in degerler if v not in digerleri] + ['Diğer']

    birlesik = {}
    for r in satirlar:
        anahtar = tuple(r[f'd{n}'] for n in range(len(gruplar)))
        hedef = birlesik.setdefault(anahtar, {**{f'd{n}': anahtar[n] for n in range(len(gruplar))}, '_total': 0})
        p = 'Diğer' if r['p'] in digerleri else r['p']
        hedef[f'p::{p}'] = (hedef.get(f'p::{p}') or 0) + (r[mk] or 0)
        hedef['_total'] += r[mk] or 0
    rows = sorted(birlesik.values(), key=lambda r: -(r['_total'] or 0))
    limit = int(istek.get('limit') or 0)
    toplam_satir = len(rows)
    if limit > 0:
        rows = rows[:limit]
    tip = OLCULER[olcu][2]
    kolonlar = ([k for k in kolonlar if k['type'] == 'dim'] +
                [{'key': f'p::{v}', 'label': str(v), 'type': tip, 'pivot': v} for v in degerler] +
                [{'key': '_total', 'label': f'Toplam — {OLCULER[olcu][1]}', 'type': tip}])
    return {'columns': kolonlar, 'rows': rows, 'totals': toplam, 'row_count': toplam_satir,
            'pivot': {'by': istek.get('pivot_by'), 'measure': olcu, 'values': degerler}}


# ------------------------------------------------------------------ satir detayi
SATIR_KOLONLARI = [
    ('date', 'Tarih', 'date'), ('fiche_no', 'Fiş no', 'text'), ('direction', 'Hareket', 'text'),
    ('client', 'Müşteri / Cari', 'text'), ('client_group', 'Firma grubu', 'text'), ('city', 'Şehir', 'text'),
    ('item', 'Ürün', 'text'), ('item_code', 'Ürün kodu', 'text'), ('brand', 'Marka', 'text'),
    ('category', 'Kategori', 'text'), ('kind', 'Tür', 'text'), ('salesman', 'Temsilci', 'text'),
    ('qty', 'Adet', 'num'), ('price_tl', 'Birim fiyat (TL)', 'tl'), ('net_tl', 'Tutar (TL)', 'tl'),
    ('rate', 'USD kuru', 'num'), ('net_usd', 'Tutar (USD)', 'usd'),
    ('cost_date', 'Alış tarihi (FIFO)', 'date'), ('stock_age', 'Depoda bekleme (gün)', 'num'),
    ('cost_tl', 'Maliyet (TL)', 'tl'), ('profit_tl', 'Brüt kâr (TL)', 'tl'),
    ('cost_usd', 'Maliyet (USD)', 'usd'), ('profit_usd', 'Brüt kâr (USD)', 'usd'),
]
SATIR_SIRALAMA = {k for k, _, _ in SATIR_KOLONLARI}


def satirlar(istek):
    where, params = kosullar(istek)
    sirala = istek.get('sort') or {}
    anahtar = sirala.get('key') if sirala.get('key') in SATIR_SIRALAMA else 'date'
    yon = 'DESC' if sirala.get('desc', True) else 'ASC'
    limit = max(1, min(int(istek.get('limit') or 200), 5000))
    offset = max(0, int(istek.get('offset') or 0))
    sql = f"""
        SELECT l.date, l.fiche_no, {BOYUTLAR['direction'][0]} AS direction,
               {BOYUTLAR['client'][0]} AS client, {BOYUTLAR['client_group'][0]} AS client_group,
               {BOYUTLAR['city'][0]} AS city, {BOYUTLAR['item'][0]} AS item, i.code AS item_code,
               {BOYUTLAR['brand'][0]} AS brand, {BOYUTLAR['category'][0]} AS category,
               {BOYUTLAR['kind'][0]} AS kind, {BOYUTLAR['salesman'][0]} AS salesman,
               {ISARET}*l.qty AS qty, l.price_tl, {ISARET}*l.net_tl AS net_tl, l.rate,
               {ISARET}*l.net_usd AS net_usd, l.cost_date,
               CASE WHEN l.cost_date IS NOT NULL THEN CAST(julianday(l.date)-julianday(l.cost_date) AS INTEGER) END
                   AS stock_age,
               CASE WHEN l.cost_complete = 1 THEN l.cost_tl END AS cost_tl,
               CASE WHEN l.cost_complete = 1 THEN l.net_tl - l.cost_tl END AS profit_tl,
               CASE WHEN l.cost_complete = 1 THEN l.cost_usd END AS cost_usd,
               CASE WHEN l.cost_complete = 1 THEN l.net_usd - l.cost_usd END AS profit_usd
        {JOINLER} WHERE {where}
        ORDER BY {anahtar} {yon}, l.line_ref DESC
        LIMIT ? OFFSET ?"""
    conn = get_db_connection()
    try:
        rows = [dict(r) for r in conn.execute(sql, params + [limit, offset]).fetchall()]
        adet = conn.execute(f"SELECT COUNT(*) {JOINLER} WHERE {where}", params).fetchone()[0]
    finally:
        conn.close()
    return {'columns': [{'key': k, 'label': lbl, 'type': t} for k, lbl, t in SATIR_KOLONLARI],
            'rows': rows, 'total': adet, 'offset': offset, 'limit': limit}


# ------------------------------------------------------------------ secenekler
def secenekler(istek=None):
    """Filtre kutulari icin degerler ve kayit sayilari (istege bagli donem icinde)."""
    istek = dict(istek or {})
    istek.setdefault('direction', 'TUMU')
    sonuc = {}
    conn = get_db_connection()
    try:
        for boyut in ('brand', 'category', 'kind', 'revenue_type', 'salesman', 'city', 'client_group', 'year'):
            alt = {**istek, 'filters': {k: v for k, v in (istek.get('filters') or {}).items() if k != boyut}}
            where, params = kosullar(alt)
            sql = (f"SELECT {BOYUTLAR[boyut][0]} AS v, COUNT(*) AS n, SUM({ISARET}*l.net_tl) AS t {JOINLER} "
                   f"WHERE {where} GROUP BY v ORDER BY t DESC")
            sonuc[boyut] = [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
    return sonuc


def deger_ara(boyut, metin, limit=30):
    """Musteri / urun gibi binlerce degeri olan boyutlar icin arama."""
    if boyut not in ('client', 'item', 'client_group', 'item_code'):
        raise GecersizIstek('Bu boyut için arama yok.')
    conn = get_db_connection()
    try:
        ifade = BOYUTLAR[boyut][0]
        rows = conn.execute(
            f"SELECT {ifade} AS v, COUNT(*) AS n {JOINLER} WHERE l.cancelled = 0 AND {ifade} LIKE ? "
            f"GROUP BY v ORDER BY n DESC LIMIT ?", (f'%{metin}%', limit)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def veri_araligi():
    conn = get_db_connection()
    try:
        r = conn.execute("SELECT MIN(date) AS ilk, MAX(date) AS son, COUNT(*) AS satir FROM wh_lines "
                         "WHERE cancelled = 0").fetchone()
        son_sync = conn.execute("SELECT * FROM sync_log ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
    return {'first': r['ilk'], 'last': r['son'], 'lines': r['satir'],
            'last_sync': dict(son_sync) if son_sync else None}


# ------------------------------------------------------------------ stok
def stok(istek):
    """Belirli bir tarihteki eldeki stok, urun bazinda.

    Deger: eldeki adet x o tarihe kadarki SON alis birim maliyeti (yaklasik;
    FIFO kalan lotlarin tam degeri degil — arayuzde boyle etiketlenir).
    """
    tarih = _tarih(istek.get('as_of'), date.today().isoformat())
    hiz_gun = int(istek.get('velocity_days') or 90)
    hiz_bas = (date.fromisoformat(tarih) - timedelta(days=hiz_gun)).isoformat()
    where = ["l.cancelled = 0", "l.linetype = 0", "l.item_ref > 0", "l.date <= ?"]
    params = [tarih]
    for boyut in ('brand', 'category', 'kind', 'item'):
        degerler = (istek.get('filters') or {}).get(boyut)
        if degerler:
            where.append(f"{BOYUTLAR[boyut][0]} IN ({','.join('?' * len(degerler))})")
            params += list(degerler)
    arama = (istek.get('search') or '').strip()
    if arama:
        for kelime in arama.split():
            where.append("(i.name LIKE ? OR i.code LIKE ?)")
            params += [f'%{kelime}%'] * 2
    sql = f"""
        SELECT l.item_ref, i.name AS item, i.code AS item_code, COALESCE(i.brand,'Markasız') AS brand,
               COALESCE(i.category,'Diğer') AS category,
               SUM(CASE WHEN l.iocode IN (1,2) THEN l.qty WHEN l.iocode IN (3,4) THEN -l.qty ELSE 0 END) AS qty,
               MAX(CASE WHEN l.direction = 'ALIS' THEN l.date END) AS last_purchase,
               MAX(CASE WHEN l.direction = 'SATIS' THEN l.date END) AS last_sale,
               MAX(l.date) AS last_move,
               SUM(CASE WHEN l.direction = 'SATIS' AND l.date >= ? THEN l.qty ELSE 0 END) AS sold_recent
        FROM wh_lines l JOIN wh_items i ON i.item_ref = l.item_ref
        WHERE {' AND '.join(where)}
        GROUP BY l.item_ref"""
    conn = get_db_connection()
    try:
        rows = [dict(r) for r in conn.execute(sql, [hiz_bas] + params).fetchall()]
        son_maliyet = {r['item_ref']: (r['birim'], r['birim_usd']) for r in conn.execute("""
            SELECT l.item_ref, l.net_tl / l.qty AS birim, l.net_usd / l.qty AS birim_usd
            FROM wh_lines l
            JOIN (SELECT item_ref, MAX(date) AS d FROM wh_lines
                  WHERE direction = 'ALIS' AND cancelled = 0 AND qty > 0 AND date <= ? GROUP BY item_ref) son
              ON son.item_ref = l.item_ref AND son.d = l.date
            WHERE l.direction = 'ALIS' AND l.cancelled = 0 AND l.qty > 0""", (tarih,)).fetchall()}
    finally:
        conn.close()

    sadece_eldeki = istek.get('only_in_stock', True)
    bugun = date.fromisoformat(tarih)
    sonuc = []
    for r in rows:
        if sadece_eldeki and (r['qty'] or 0) <= 0.0001:
            continue
        birim, birim_usd = son_maliyet.get(r['item_ref'], (None, None))
        r['unit_cost_tl'] = birim
        r['value_tl'] = (birim or 0) * (r['qty'] or 0) if birim else None
        r['value_usd'] = (birim_usd or 0) * (r['qty'] or 0) if birim_usd else None
        r['days_since_move'] = (bugun - date.fromisoformat(r['last_move'])).days if r['last_move'] else None
        r['cover_days'] = (round(r['qty'] / (r['sold_recent'] / hiz_gun)) if r['sold_recent'] else None)
        sonuc.append(r)
    sirala = istek.get('sort') or {}
    anahtar = sirala.get('key') or 'value_tl'
    sonuc.sort(key=lambda r: (r.get(anahtar) is None, r.get(anahtar) or 0), reverse=sirala.get('desc', True))
    sonuc.sort(key=lambda r: r.get(anahtar) is None)
    toplam = {
        'items': len(sonuc), 'qty': sum(r['qty'] or 0 for r in sonuc),
        'value_tl': sum(r['value_tl'] or 0 for r in sonuc), 'value_usd': sum(r['value_usd'] or 0 for r in sonuc),
        'dead_items': sum(1 for r in sonuc if (r['days_since_move'] or 0) > 180),
        'dead_value_tl': sum(r['value_tl'] or 0 for r in sonuc if (r['days_since_move'] or 0) > 180),
    }
    limit = int(istek.get('limit') or 0)
    return {'as_of': tarih, 'velocity_days': hiz_gun, 'rows': sonuc[:limit] if limit else sonuc, 'totals': toplam}


def stok_grup_ozeti(tarih, boyut='category'):
    """Belirli tarihteki stok miktari/degerinin kirilima gore toplami (donem raporu icin)."""
    s = stok({'as_of': tarih})
    gruplar = {}
    for r in s['rows']:
        g = gruplar.setdefault(r.get(boyut) or 'Diğer', {'qty': 0, 'value_tl': 0, 'value_usd': 0, 'items': 0})
        g['qty'] += r['qty'] or 0
        g['value_tl'] += r['value_tl'] or 0
        g['value_usd'] += r['value_usd'] or 0
        g['items'] += 1
    return gruplar, s['totals']


# ------------------------------------------------------------------ donem raporu
def donem_raporu(istek):
    """Ay sonu raporu: alislar, satislar, donem basi ve sonu stok — secilen kirilima gore."""
    bas = _tarih(istek.get('date_from'), date.today().replace(day=1).isoformat())
    bit = _tarih(istek.get('date_to'), date.today().isoformat())
    boyut = istek.get('group_by') or 'category'
    if boyut not in ('category', 'brand', 'kind', 'revenue_type'):
        raise GecersizIstek('Dönem raporu kategori, marka, tür ya da gelir tipine göre kırılabilir.')
    filtreler = istek.get('filters') or {}
    temel = {'date_from': bas, 'date_to': bit, 'filters': filtreler}

    alis = sorgu({**temel, 'direction': 'ALIS_NET', 'group_by': [boyut],
                  'measures': ['qty', 'net_tl', 'net_usd', 'invoices']})
    satis = sorgu({**temel, 'direction': 'SATIS_NET', 'group_by': [boyut],
                   'measures': ['qty', 'net_tl', 'net_usd', 'cost_tl', 'profit_tl', 'margin', 'invoices', 'clients']})
    onceki_gun = (date.fromisoformat(bas) - timedelta(days=1)).isoformat()
    acilis, acilis_top = stok_grup_ozeti(onceki_gun, boyut)
    kapanis, kapanis_top = stok_grup_ozeti(bit, boyut)

    tum = set(acilis) | set(kapanis) | {r['d0'] for r in alis['rows']} | {r['d0'] for r in satis['rows']}
    a_map = {r['d0']: r for r in alis['rows']}
    s_map = {r['d0']: r for r in satis['rows']}
    satirlar_ = []
    for g in tum:
        a, s = a_map.get(g, {}), s_map.get(g, {})
        satirlar_.append({
            'group': g,
            'open_qty': acilis.get(g, {}).get('qty', 0), 'open_value_tl': acilis.get(g, {}).get('value_tl', 0),
            'buy_qty': a.get('m_qty') or 0, 'buy_tl': a.get('m_net_tl') or 0, 'buy_usd': a.get('m_net_usd') or 0,
            'sell_qty': s.get('m_qty') or 0, 'sell_tl': s.get('m_net_tl') or 0, 'sell_usd': s.get('m_net_usd') or 0,
            'profit_tl': s.get('m_profit_tl'), 'margin': s.get('m_margin'),
            'close_qty': kapanis.get(g, {}).get('qty', 0), 'close_value_tl': kapanis.get(g, {}).get('value_tl', 0),
            'close_value_usd': kapanis.get(g, {}).get('value_usd', 0),
        })
    satirlar_.sort(key=lambda r: -(r['sell_tl'] + r['buy_tl']))

    en_cok = lambda yon, gb, olcu: sorgu({**temel, 'direction': yon, 'group_by': [gb], 'measures': [olcu, 'net_usd'],
                                          'limit': 10})['rows']
    return {
        'date_from': bas, 'date_to': bit, 'group_by': boyut, 'group_label': BOYUTLAR[boyut][1],
        'rows': satirlar_,
        'totals': {
            'open_value_tl': acilis_top['value_tl'], 'close_value_tl': kapanis_top['value_tl'],
            'close_value_usd': kapanis_top['value_usd'],
            'open_qty': acilis_top['qty'], 'close_qty': kapanis_top['qty'],
            'buy_tl': alis['totals'].get('m_net_tl') or 0, 'buy_usd': alis['totals'].get('m_net_usd') or 0,
            'buy_invoices': alis['totals'].get('m_invoices') or 0,
            'sell_tl': satis['totals'].get('m_net_tl') or 0, 'sell_usd': satis['totals'].get('m_net_usd') or 0,
            'profit_tl': satis['totals'].get('m_profit_tl'), 'margin': satis['totals'].get('m_margin'),
            'sell_invoices': satis['totals'].get('m_invoices') or 0, 'clients': satis['totals'].get('m_clients') or 0,
        },
        'top_customers': en_cok('SATIS_NET', 'client', 'net_tl'),
        'top_suppliers': en_cok('ALIS_NET', 'client', 'net_tl'),
        'top_items_sold': en_cok('SATIS_NET', 'item', 'net_tl'),
        'top_items_bought': en_cok('ALIS_NET', 'item', 'net_tl'),
    }


# ------------------------------------------------------------------ genel bakis
def onceki_donem(bas, bit):
    b, e = date.fromisoformat(bas), date.fromisoformat(bit)
    gun = (e - b).days + 1
    return (b - timedelta(days=gun)).isoformat(), (b - timedelta(days=1)).isoformat()


def genel_bakis(istek):
    bas = _tarih(istek.get('date_from'), (date.today() - timedelta(days=365)).isoformat())
    bit = _tarih(istek.get('date_to'), date.today().isoformat())
    filtreler = istek.get('filters') or {}
    karsi = istek.get('compare', 'previous')    # 'previous' | 'year' | 'none'
    if karsi == 'year':
        kb = date.fromisoformat(bas).replace(year=date.fromisoformat(bas).year - 1).isoformat()
        ke = date.fromisoformat(bit).replace(year=date.fromisoformat(bit).year - 1).isoformat()
    else:
        kb, ke = onceki_donem(bas, bit)

    olc = ['net_tl', 'net_usd', 'qty', 'profit_tl', 'margin', 'invoices', 'clients', 'items']

    def ozet(b, e):
        s = sorgu({'date_from': b, 'date_to': e, 'filters': filtreler, 'direction': 'SATIS_NET',
                   'group_by': ['revenue_type'], 'measures': olc})
        a = sorgu({'date_from': b, 'date_to': e, 'filters': filtreler, 'direction': 'ALIS_NET',
                   'measures': ['net_tl', 'net_usd', 'invoices']})
        return {'sales': s['totals'], 'by_revenue_type': {r['d0']: r for r in s['rows']}, 'purchases': a['totals']}

    simdi = ozet(bas, bit)
    once = ozet(kb, ke) if karsi != 'none' else None

    # zaman serisi: donem uzunluguna gore otomatik kirilim (kullanici degistirebilir)
    gun = (date.fromisoformat(bit) - date.fromisoformat(bas)).days
    kirilim = istek.get('granularity') or ('day' if gun <= 45 else 'week' if gun <= 200 else 'month' if gun <= 1100
                                           else 'quarter' if gun <= 2500 else 'year')
    seri_satis = sorgu({'date_from': bas, 'date_to': bit, 'filters': filtreler, 'direction': 'SATIS_NET',
                        'group_by': [kirilim], 'pivot_by': 'revenue_type', 'measures': [istek.get('measure') or 'net_tl']})
    seri_alis = sorgu({'date_from': bas, 'date_to': bit, 'filters': filtreler, 'direction': 'ALIS_NET',
                       'group_by': [kirilim], 'measures': [istek.get('measure') or 'net_tl']})
    en_iyi = lambda gb: sorgu({'date_from': bas, 'date_to': bit, 'filters': filtreler, 'direction': 'SATIS_NET',
                               'group_by': [gb], 'measures': ['net_tl', 'net_usd', 'profit_tl', 'margin'],
                               'limit': 8})['rows']
    return {
        'date_from': bas, 'date_to': bit, 'compare_from': kb, 'compare_to': ke, 'compare': karsi,
        'current': simdi, 'previous': once, 'granularity': kirilim,
        'series_sales': seri_satis, 'series_purchases': seri_alis,
        'top_brands': en_iyi('brand'), 'top_categories': en_iyi('category'),
        'top_customers': en_iyi('client_group'), 'top_salesmen': en_iyi('salesman'),
    }


def meta():
    return {
        'dimensions': [{'key': k, 'label': v[1], 'filterable': k in FILTRE_BOYUTLARI} for k, v in BOYUTLAR.items()],
        'measures': [{'key': k, 'label': v[1], 'type': v[2]} for k, v in OLCULER.items()],
        'directions': [
            {'key': 'SATIS_NET', 'label': 'Satış (iadeler düşülmüş)'}, {'key': 'SATIS', 'label': 'Satış (brüt)'},
            {'key': 'ALIS_NET', 'label': 'Alış (iadeler düşülmüş)'}, {'key': 'ALIS', 'label': 'Alış (brüt)'},
            {'key': 'TUMU', 'label': 'Tüm hareketler'},
        ],
    }
