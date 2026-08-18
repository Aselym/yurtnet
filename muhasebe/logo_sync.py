"""Logo ERP (MS SQL Server) okuma katmani.

Logo tarafina asla yazilmaz: baglanti salt-okunur bir hesapla kurulur ve tum
sorgular WITH (NOLOCK) ile calisir, boylece muhasebe ekibi Logo'da fatura
keserken kilitlenme yasanmaz.

Iki ayri urun grubu var ve takip mantiklari farkli:

  1. Sureli lisanslar (WatchGuard, FortiGate, ESET, Veeam, PLOG...)
     Tek seferde 1 veya 3 yilligina satilir, bitince yenilenmesi gerekir.
     Logo bitis tarihini TUTMUYOR (ESTARTDATE/EENDDATE alanlari bos) — bu
     yuzden sureyi urun adindan cikariyoruz: "1YIL", "3 YILLIK", "LIC3Y".
     Cikarilamayanlar NEEDS_DURATION ile isaretlenir ve elle sure girilene
     kadar hatirlatma uretmez; yanlis tarihle yanlis uyari gitmesin.

  2. Aylik abonelikler (Microsoft CSP, Azure)
     Her ay yeniden faturalanir, "suresi dolmaz". Burada aranan sey fatura
     kesilmenin DURMASI: musteri abonelikten cikmis olabilir.
"""

import re
from datetime import datetime

from database import get_db_connection, calculate_dates, sure_dolmuslari_isaretle

# Sureli lisans urunlerini yakalayan kelimeler.
#
# Bu bir BEYAZ LISTE ve oyle kalmali: urun adinda "3YIL" gecmesi lisans
# oldugu anlamina gelmiyor. "DELL LATI 3450 ... 3YIL" bir dizustu bilgisayarin
# garanti suresi, "TOSHIBA 16TB GUVENLIK HDD" bir disk. Marka bazli
# eslestirme bizi bu tur yanlis pozitiflerden koruyor.
#
# Yazim hatali varyantlar da listede: gercek veride "WATCGUARD",
# "WATCGHUARD" ve "FOTIGATE" seklinde girilmis kayitlar var.
LISANS_MARKALARI = [
    'WATCHGUARD', 'WATCGUARD', 'WATCGHUARD',
    'FORTIGATE', 'FOTIGATE', 'FORTINET',
    'SOPHOS', 'ESET', 'KASPERSKY', 'BITDEFENDER', 'TRELLIX',
    'COMODO', 'XCITIUM', 'SAFETICA',
    'VEEAM', 'VMWARE',
    'PLOG', '5651', 'SIGNLOGGER', 'CRYPTTECH',
    'ADOBE', 'AUTOCAD', 'AUTODESK', 'GEOTRUST',
]

# Aylik abonelik urunleri
ABONELIK_MARKALARI = ['MICROSOFT', 'AZURE', 'CSP']

# Tek seferlik/kalici lisanslar: birden fazla kez satilmis olabilirler ama
# abonelik degildirler. "Fatura kesilmeyi birakti" uyarisi bunlar icin yanlis
# olur — musteri sadece o donem baska bilgisayar almamistir.
KALICI_LISANS_KELIMELERI = [
    'OEM', 'ESD', 'PERP', 'PERPETUAL', 'GGWA', 'FQC-', 'RETAIL', 'ROK',
]

# Gercek aylik abonelik sayilmasi icin asgari kosullar
ABONELIK_MIN_FATURA = 4       # en az bu kadar kez faturalanmis olmali
ABONELIK_MAX_ARALIK_GUN = 60  # ortalama faturalama araligi bunu asmamali

# Bunlar donanim; lisans degil, yenileme takibi gerektirmez.
# Gercek veride "APPLIANCE ONLY" birden fazla yazimla geciyor: bosluksuz
# ("APPLIANCEONLY"), kisaltilmis ("APPLIENCE ONL") ve harf hatali
# ("APLLIANCE"). Bu yuzden asagida bosluklar silinerek karsilastiriliyor.
DONANIM_KELIMELERI = [
    'APPLIANCEONLY', 'APPLIENCEONLY', 'APLLIANCEONLY', 'APPLIENCEONL',
    'APPLIANCEONL', 'POEAPPLIANCE', 'HARDWARETOKEN',
    'TRANSCEIVER', 'SFP', 'SWITCH', 'ACCESSPOINT', 'POWERINJEKTOR',
    'INJEKTOR', 'INJECTOR', 'RACKMOUNT', 'RACKTRAY', 'MODUL', 'MODULE',
    'CIHAZ', 'KLAVYE', 'MONITOR', 'MONITÖR', 'TABLET', 'KABLO', 'PATCHPANEL',
]

SATIS_TRCODE = (7, 8, 9)  # perakende satis, toptan satis, verilen hizmet


def get_logo_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}


def build_connection_string(settings):
    server = settings.get('logo_sql_server', '127.0.0.1')
    port = settings.get('logo_sql_port', '1433')
    database = settings.get('logo_sql_db', 'LOGO')
    user = settings.get('logo_sql_user', 'sa')
    password = settings.get('logo_sql_pass', '')

    driver_name = 'SQL Server'
    try:
        import pyodbc
        mevcut = pyodbc.drivers()
        for d in ('ODBC Driver 18 for SQL Server',
                  'ODBC Driver 17 for SQL Server',
                  'SQL Server'):
            if d in mevcut:
                driver_name = d
                break
    except Exception:
        pass

    ek = 'Encrypt=no;TrustServerCertificate=yes;' if '18' in driver_name else ''

    return (f"DRIVER={{{driver_name}}};SERVER={server},{port};DATABASE={database};"
            f"UID={user};PWD={password};{ek}Timeout=10;")


def _baglan():
    """Salt-okunur Logo baglantisi.

    Metin sutunlari sorgularda CAST(... AS NVARCHAR) ile cekiliyor; boylece
    donusumu SQL Server kendi collation bilgisiyle yapiyor ve Turkce
    karakterler dogru geliyor. Istemci tarafinda kod sayfasi zorlamak
    (setdecoding cp1254) kirilgandi: urun adlarindan birinde cp1254'te
    karsiligi olmayan bir bayt vardi ve tum senkronizasyonu cokertiyordu.
    """
    import pyodbc
    return pyodbc.connect(build_connection_string(get_logo_settings()))


def test_logo_connection():
    try:
        conn = _baglan()
        cur = conn.cursor()
        ayarlar = get_logo_settings()
        firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
        donem = (ayarlar.get('logo_period_no') or '01').zfill(2)
        cur.execute(f'SELECT COUNT(*) FROM LG_{firma}_{donem}_INVOICE WITH (NOLOCK)')
        adet = cur.fetchone()[0]
        conn.close()
        return True, f"Bağlantı başarılı. Firma {firma}/{donem} içinde {adet:,} fatura bulundu."
    except ImportError:
        return False, "pyodbc kütüphanesi yüklü değil. (pip install pyodbc)"
    except Exception as e:
        return False, f"SQL bağlantı hatası: {e}"


def sure_ay_bul(urun_adi):
    """Urun adindan lisans suresini ay cinsinden cikarir; bulunamazsa None.

    Gercek veriden ogrenilen kaliplar: "1YIL", "3 YILLIK", "3YEAR", "1 YEAR",
    tireli "3-Y", kisaltilmis "1YR", yazim hatali "1TEAR" ve bosluksuz
    yazimlar ("GUVLIC3Y", "FAORTIAUTH.3Y").
    """
    m = (urun_adi or '').upper()

    # YIL / YILLIK / YEAR / YEARS ve "1TEAR" gibi harf hatalari.
    # Sonrasina sinir konmaz: "3 YILLIK" ve "1YEARS" da eslesmeli.
    yil = re.search(r'(\d+)\s*[-\s]*(?:YIL|YEAR|TEAR)', m)
    if yil:
        return int(yil.group(1)) * 12

    # "1YR" — kisaltma; burada sinir sart, "1YRX" gibi SKU'ya takilmasin
    yr = re.search(r'(\d+)\s*[-\s]*YR(?![A-Z0-9])', m)
    if yr:
        return int(yr.group(1)) * 12

    ay = re.search(r'(\d+)\s*(?:AY|MONTH)', m)
    if ay:
        return int(ay.group(1))

    # Tireli yazim: "M395 - 3-Y WGM395160"
    tireli = re.search(r'(?<!\d)(\d)\s*-\s*Y(?![A-Z0-9])', m)
    if tireli:
        return int(tireli.group(1)) * 12

    # "3Y" — tek rakam + Y. Ardindan harf/rakam gelmemeli ki "WGT1850203"
    # gibi model kodlari ve "SU1YP-00" gibi SKU'lar yanlislikla eslesmesin.
    kisa = re.search(r'(?<!\d)(\d)Y(?![A-Z0-9])', m)
    if kisa:
        return int(kisa.group(1)) * 12

    return None


def _donanim_mi(urun_adi):
    # Bosluklar ve noktalama silinerek karsilastirilir: gercek veride
    # "APPLIENCE  ONL" gibi cift bosluklu ve kesik yazimlar var.
    m = re.sub(r'[^A-Z0-9]', '', (urun_adi or '').upper())
    return any(k in m for k in DONANIM_KELIMELERI)


def _kalici_lisans_mi(urun_adi):
    m = (urun_adi or '').upper()
    return any(k in m for k in KALICI_LISANS_KELIMELERI)


def _like_kosulu(markalar, alan='ITM.NAME'):
    return ' OR '.join(f"{alan} LIKE '%{k}%'" for k in markalar)


def _temiz_metin(deger):
    metin = (deger or '').strip()
    return '' if metin in ('-', '.', '_') else metin


def _temiz_mail(deger):
    return _temiz_metin(deger)


# Bitisi bu tarihten onceye dusen lisanslar alinmaz. Coktan gecmis bir
# yenileme firsati listeyi sisirmekten baska ise yaramiyor: satis ekibi
# 2025'te dolmus bir lisans icin bugun musteriyi aramayacak.
EN_ESKI_BITIS = '2026-01-01'


def sync_logo_invoices(gecmis_yil=3, en_eski_bitis=EN_ESKI_BITIS):
    """Sureli lisans satislarini Logo'dan cekip yerel veritabanina yazar.

    Bitisi `en_eski_bitis` tarihinden onceye dusenler atlanir.
    Doner: (eklenen, sure_bekleyen, atlanan)
    """
    ayarlar = get_logo_settings()
    firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
    donem = (ayarlar.get('logo_period_no') or '01').zfill(2)

    conn = _baglan()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT INV.FICHENO, INV.DATE_, STL.LOGICALREF AS satir_ref,
               CAST(CLC.DEFINITION_ AS NVARCHAR(200)) AS cari_ad,
               CAST(CLC.EMAILADDR AS NVARCHAR(200))    AS cari_mail,
               CAST(CLC.CODE AS NVARCHAR(50))          AS cari_kod,
               CAST(CLC.TELNRS1 AS NVARCHAR(50))       AS cari_tel,
               CAST(CLC.CITY AS NVARCHAR(50))          AS cari_sehir,
               CAST(ITM.NAME AS NVARCHAR(200))         AS urun_adi,
               CAST(ITM.CODE AS NVARCHAR(50))          AS urun_kod,
               CAST(SLS.DEFINITION_ AS NVARCHAR(100))  AS temsilci,
               STL.TOTAL                               AS satir_tutar
        FROM LG_{firma}_{donem}_INVOICE INV WITH (NOLOCK)
        JOIN LG_{firma}_{donem}_STLINE STL WITH (NOLOCK)
             ON STL.INVOICEREF = INV.LOGICALREF
        JOIN LG_{firma}_ITEMS ITM WITH (NOLOCK)
             ON ITM.LOGICALREF = STL.STOCKREF
        LEFT JOIN LG_{firma}_CLCARD CLC WITH (NOLOCK)
             ON CLC.LOGICALREF = INV.CLIENTREF
        LEFT JOIN LG_SLSMAN SLS WITH (NOLOCK)
             ON SLS.LOGICALREF = INV.SALESMANREF
        WHERE INV.TRCODE IN {SATIS_TRCODE}
          AND INV.CANCELLED = 0
          AND INV.DATE_ >= DATEADD(year, -{int(gecmis_yil)}, GETDATE())
          AND ({_like_kosulu(LISANS_MARKALARI)})
        ORDER BY INV.DATE_ DESC
    """)
    satirlar = cur.fetchall()
    conn.close()

    yerel = get_db_connection()
    yc = yerel.cursor()
    eklenen = sure_bekleyen = atlanan = 0

    for r in satirlar:
        urun = (r.urun_adi or '').strip()
        if not urun or _donanim_mi(urun):
            atlanan += 1
            continue

        logo_ref = f"{r.FICHENO}#{r.satir_ref}"
        yc.execute('SELECT 1 FROM sales WHERE logo_ref = ?', (logo_ref,))
        if yc.fetchone():
            atlanan += 1
            continue

        satis_tarihi = r.DATE_.strftime('%Y-%m-%d')
        cari = (r.cari_ad or 'Bilinmeyen Müşteri').strip()
        mail = _temiz_mail(r.cari_mail)
        telefon = _temiz_metin(r.cari_tel)
        sehir = _temiz_metin(r.cari_sehir)

        ay = sure_ay_bul(urun)
        if ay:
            bitis = calculate_dates(satis_tarihi, ay)
            if bitis < en_eski_bitis:
                atlanan += 1
                continue
            durum = 'PENDING'
            sure_tipi = {12: '1_YEAR', 24: '2_YEARS',
                         36: '3_YEARS', 60: '5_YEARS'}.get(ay, 'CUSTOM')
        else:
            # Sure bilinmiyor: en iyimser tahminle 3 yillik olsa bile
            # esikten eskiyse artik ilgilendirmiyor demektir.
            if calculate_dates(satis_tarihi, 36) < en_eski_bitis:
                atlanan += 1
                continue
            # Bitis olarak satis tarihi konur ama NEEDS_DURATION durumu
            # hatirlatma uretilmesini engeller.
            ay, bitis = 0, satis_tarihi
            durum, sure_tipi = 'NEEDS_DURATION', 'CUSTOM'
            sure_bekleyen += 1

        temsilci = (r.temsilci or '').strip()
        fiyat = float(r.satir_tutar) if r.satir_tutar else None

        yc.execute('''
            INSERT INTO sales (product_name, client_name, client_email, sales_rep,
                               license_key, sale_date, duration_type, duration_months,
                               expiration_date, reminder_type, status, notes,
                               logo_ref, source, price, client_phone, client_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'STAGED', ?, ?, ?, 'LOGO', ?, ?, ?)
        ''', (urun, cari, mail, temsilci, (r.urun_kod or '').strip(), satis_tarihi,
              sure_tipi, ay, bitis, durum,
              f"Logo faturası {r.FICHENO} (cari {r.cari_kod or '-'})", logo_ref, fiyat,
              telefon, sehir))
        eklenen += 1

    yerel.commit()
    yerel.close()

    # Cekilen kayitlarin bir kismi zaten gecmis tarihli olabilir.
    sure_dolmuslari_isaretle()
    return eklenen, sure_bekleyen, atlanan


def sync_logo_subscriptions(gecmis_yil=2, risk_kat=2.0):
    """Aylik abonelikleri musteri+urun bazinda ozetler.

    Her abonelik icin ortalama faturalama araligi hesaplanir. Son faturanin
    uzerinden bu araligin `risk_kat` katindan fazla zaman gectiyse abonelik
    riskli, iki katindan fazlaysa kayip sayilir.

    Doner: (yazilan, riskli)
    """
    ayarlar = get_logo_settings()
    firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
    donem = (ayarlar.get('logo_period_no') or '01').zfill(2)

    conn = _baglan()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT CAST(CLC.DEFINITION_ AS NVARCHAR(200)) AS cari_ad,
               CAST(CLC.EMAILADDR AS NVARCHAR(200))    AS cari_mail,
               CAST(CLC.TELNRS1 AS NVARCHAR(50))       AS cari_tel,
               CAST(CLC.CITY AS NVARCHAR(50))          AS cari_sehir,
               CAST(ITM.NAME AS NVARCHAR(200))         AS urun_adi,
               COUNT(*) AS adet,
               MIN(INV.DATE_) AS ilk_tarih,
               MAX(INV.DATE_) AS son_tarih
        FROM LG_{firma}_{donem}_INVOICE INV WITH (NOLOCK)
        JOIN LG_{firma}_{donem}_STLINE STL WITH (NOLOCK)
             ON STL.INVOICEREF = INV.LOGICALREF
        JOIN LG_{firma}_ITEMS ITM WITH (NOLOCK)
             ON ITM.LOGICALREF = STL.STOCKREF
        LEFT JOIN LG_{firma}_CLCARD CLC WITH (NOLOCK)
             ON CLC.LOGICALREF = INV.CLIENTREF
        WHERE INV.TRCODE IN {SATIS_TRCODE}
          AND INV.CANCELLED = 0
          AND INV.DATE_ >= DATEADD(year, -{int(gecmis_yil)}, GETDATE())
          AND ({_like_kosulu(ABONELIK_MARKALARI)})
        GROUP BY CAST(CLC.DEFINITION_ AS NVARCHAR(200)),
                 CAST(CLC.EMAILADDR AS NVARCHAR(200)),
                 CAST(CLC.TELNRS1 AS NVARCHAR(50)),
                 CAST(CLC.CITY AS NVARCHAR(50)),
                 CAST(ITM.NAME AS NVARCHAR(200))
        HAVING COUNT(*) >= 2
        ORDER BY MAX(INV.DATE_) DESC
    """)
    satirlar = cur.fetchall()
    conn.close()

    bugun = datetime.now().date()
    yerel = get_db_connection()
    yc = yerel.cursor()
    yazilan = riskli = 0

    for r in satirlar:
        urun = (r.urun_adi or '').strip()
        cari = (r.cari_ad or 'Bilinmeyen Müşteri').strip()
        if not urun or _donanim_mi(urun) or _kalici_lisans_mi(urun):
            continue

        ilk, son = r.ilk_tarih.date(), r.son_tarih.date()
        adet = int(r.adet)

        gun_farki = (son - ilk).days
        ortalama = (gun_farki / (adet - 1)) if adet > 1 and gun_farki > 0 else 30.0
        gecen = (bugun - son).days

        # Duzenli abonelik oruntusu yoksa (az fatura ya da seyrek araliklarla)
        # bu bir abonelik degil, ara ara yapilan alimdir.
        if adet < ABONELIK_MIN_FATURA or ortalama > ABONELIK_MAX_ARALIK_GUN:
            continue

        # Uzun suredir fatura kesilmemis: abonelik bitmis demektir, takip
        # listesinde yeri yok. Kaydedilmiyor ki liste yalnizca hala devam
        # eden ve riske girenlerden olussun.
        if gecen > ortalama * risk_kat * 2:
            continue

        if gecen > ortalama * risk_kat:
            durum = 'AT_RISK'
            riskli += 1
        else:
            durum = 'ACTIVE'

        yc.execute('''
            INSERT INTO subscriptions
                (client_name, client_email, product_name, first_invoice_date,
                 last_invoice_date, invoice_count, avg_interval_days,
                 days_since_last, status, source, updated_at, client_phone, client_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOGO', CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT (client_name, product_name) DO UPDATE SET
                client_email = excluded.client_email,
                first_invoice_date = excluded.first_invoice_date,
                last_invoice_date = excluded.last_invoice_date,
                invoice_count = excluded.invoice_count,
                avg_interval_days = excluded.avg_interval_days,
                days_since_last = excluded.days_since_last,
                status = excluded.status,
                client_phone = excluded.client_phone,
                client_city = excluded.client_city,
                updated_at = CURRENT_TIMESTAMP
        ''', (cari, _temiz_mail(r.cari_mail), urun, ilk.isoformat(),
              son.isoformat(), adet, round(ortalama, 1), gecen, durum,
              _temiz_metin(r.cari_tel), _temiz_metin(r.cari_sehir)))
        yazilan += 1

    yerel.commit()
    yerel.close()
    return yazilan, riskli


# ---------------------------------------------------------------- yenileme

# Ayni islevi goren urunler ayni kategoriye dusmeli ki urun kodu degisse bile
# yenileme yakalanabilsin: WGEPDR30201 -> WGESB30201 (EPDR, "Endpoint Security
# 360" adini almis) ya da PLOG 5651 -> SIGNLOGGER 5651 (marka degismis).
YENILEME_KATEGORILERI = [
    ('endpoint', ('EPDR', 'ESB', 'ENDPOINT', 'EPP', 'PATCH MANAGEMENT', 'WGPTCH')),
    ('log5651',  ('5651', 'PLOG', 'SIGNLOGGER', 'HOTSPOT')),
    ('mfa',      ('AUTHPOINT', 'WGATH')),
    ('backup',   ('VEEAM', 'BACKUP')),
    ('dns',      ('DNSWATCH', 'WGDNS')),
]

FIREWALL_IPUCU = ('WATCHGUARD', 'WATCGUARD', 'FIREBOX', 'FORTIGATE')

# Firebox model kodu: WGT25341, WGM27333, WGVME331... Model onemli, cunku bir
# musteride birden fazla cihaz olabilir (T25 ve T85 gibi) ve bunlar birbirini
# yenilemez.
_MODEL_DESEN = re.compile(r'WG([TMV][A-Z]*\d+|ME\d*)')


def yenileme_kategorisi(urun_adi):
    """Yenileme eslestirmesi icin urunun islevsel kimligi."""
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
    return 'diger'


def yenileme_adaylari_bul():
    """Suresi dolmus kayitlar icin olasi yenilemeleri isaretler.

    Otomatik kapatmaz — sadece 'SUSPECT' olarak isaretler ve hangi yeni kaydin
    aday oldugunu yazar. Yanlis eslesme ihtimali var (ornegin FortiAuthenticator
    ile FortiGate destegi ayni kategoriye dusebiliyor), o yuzden son karari
    satis ekibi verir.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    kayitlar = [dict(r) for r in cur.execute('SELECT * FROM sales').fetchall()]
    for k in kayitlar:
        k['_kat'] = yenileme_kategorisi(k['product_name'])

    isaretlenen = 0
    for eski in kayitlar:
        if eski['status'] != 'EXPIRED':
            continue
        # Daha once bakilmis kayda tekrar dokunma
        if eski.get('renewal_state') in ('CONFIRMED', 'REJECTED'):
            continue

        adaylar = [
            y for y in kayitlar
            if y['id'] != eski['id']
            and y['client_name'] == eski['client_name']
            and y['_kat'] == eski['_kat']
            and y['_kat'] != 'diger'
            and (y['sale_date'] or '') > (eski['sale_date'] or '')
        ]
        if not adaylar:
            continue

        en_yeni = max(adaylar, key=lambda x: x['sale_date'])
        cur.execute(
            "UPDATE sales SET renewed_by = ?, renewal_state = 'SUSPECT' WHERE id = ?",
            (en_yeni['id'], eski['id']),
        )
        isaretlenen += 1

    conn.commit()
    conn.close()
    return isaretlenen


def sync_logo_products(gecmis_yil=2):
    """Lisans ve abonelik disindaki satis kalemlerini ceker.

    Burada yenileme/sure takibi yok — amac "bu musteriye ne satmisiz"
    sorusuna cevap vermek. Bu yuzden marka filtresi de yok: lisans ve
    abonelik markalari HARIC her sey urun sayilir.

    Doner: (eklenen, atlanan)
    """
    ayarlar = get_logo_settings()
    firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
    donem = (ayarlar.get('logo_period_no') or '01').zfill(2)

    haric = LISANS_MARKALARI + ABONELIK_MARKALARI
    haric_kosul = ' AND '.join(f"ITM.NAME NOT LIKE '%{k}%'" for k in haric)

    conn = _baglan()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT INV.FICHENO, INV.DATE_, STL.LOGICALREF AS satir_ref,
               STL.AMOUNT AS miktar, STL.PRICE AS birim_fiyat,
               STL.TOTAL AS satir_tutar,
               CAST(CLC.DEFINITION_ AS NVARCHAR(200)) AS cari_ad,
               CAST(CLC.EMAILADDR AS NVARCHAR(200))    AS cari_mail,
               CAST(CLC.TELNRS1 AS NVARCHAR(50))       AS cari_tel,
               CAST(CLC.CITY AS NVARCHAR(50))          AS cari_sehir,
               CAST(ITM.NAME AS NVARCHAR(200))         AS urun_adi,
               CAST(ITM.CODE AS NVARCHAR(50))          AS urun_kod
        FROM LG_{firma}_{donem}_INVOICE INV WITH (NOLOCK)
        JOIN LG_{firma}_{donem}_STLINE STL WITH (NOLOCK)
             ON STL.INVOICEREF = INV.LOGICALREF
        JOIN LG_{firma}_ITEMS ITM WITH (NOLOCK)
             ON ITM.LOGICALREF = STL.STOCKREF
        LEFT JOIN LG_{firma}_CLCARD CLC WITH (NOLOCK)
             ON CLC.LOGICALREF = INV.CLIENTREF
        WHERE INV.TRCODE IN {SATIS_TRCODE}
          AND INV.CANCELLED = 0
          -- Yalnizca stok kalemi satirlari. Diger satir turleri urun satisi
          -- degil: LINETYPE 8'de sirketin kendi araclarinin satisi cikti
          -- (Skoda Superb 1,7 milyon TL), LINETYPE 4'te ise tedarikcilere
          -- kesilen iade/fiyat farki satirlari var.
          AND STL.LINETYPE = 0
          AND INV.DATE_ >= DATEADD(year, -{int(gecmis_yil)}, GETDATE())
          AND {haric_kosul}
        ORDER BY INV.DATE_ DESC
    """)
    satirlar = cur.fetchall()
    conn.close()

    yerel = get_db_connection()
    yc = yerel.cursor()
    eklenen = atlanan = 0

    for r in satirlar:
        urun = (r.urun_adi or '').strip()
        if not urun:
            atlanan += 1
            continue

        logo_ref = f"{r.FICHENO}#{r.satir_ref}"
        yc.execute('SELECT 1 FROM products WHERE logo_ref = ?', (logo_ref,))
        if yc.fetchone():
            atlanan += 1
            continue

        yc.execute("""
            INSERT INTO products (product_name, product_code, client_name, client_email,
                                  quantity, unit_price, line_total, sale_date,
                                  invoice_no, logo_ref, source, client_phone, client_city)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOGO', ?, ?)
        """, (
            urun, (r.urun_kod or '').strip(),
            (r.cari_ad or 'Bilinmeyen Müşteri').strip(), _temiz_mail(r.cari_mail),
            float(r.miktar or 0), float(r.birim_fiyat or 0), float(r.satir_tutar or 0),
            r.DATE_.strftime('%Y-%m-%d'), (r.FICHENO or '').strip(), logo_ref,
            _temiz_metin(r.cari_tel), _temiz_metin(r.cari_sehir),
        ))
        eklenen += 1

    yerel.commit()
    yerel.close()
    return eklenen, atlanan


if __name__ == '__main__':
    ok, mesaj = test_logo_connection()
    print(mesaj)
    if ok:
        e, s, a = sync_logo_invoices()
        print(f'Lisans : {e} eklendi ({s} süre bekliyor), {a} atlandı')
        y, r = sync_logo_subscriptions()
        print(f'Abonelik: {y} kayıt, {r} riskli')
        u, ua = sync_logo_products()
        print(f'Ürün    : {u} eklendi, {ua} atlandı')
