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

from database import get_db_connection, calculate_dates

# Sureli lisans urunlerini yakalayan kelimeler
LISANS_MARKALARI = [
    'WATCHGUARD', 'WATCGUARD', 'FORTIGATE', 'FORTINET', 'SOPHOS', 'ESET',
    'KASPERSKY', 'VEEAM', 'PLOG', '5651', 'SIGNLOGGER', 'CRYPTTECH',
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

# Bunlar donanim; lisans degil, yenileme takibi gerektirmez
DONANIM_KELIMELERI = [
    'APPLIANCE ONLY', 'APPLIENCE ONLY', 'TRANSCEIVER', 'SFP', 'SWITCH',
    'ACCESS POINT', 'POWER INJEKTOR', 'INJECTOR', 'RACK MOUNT', 'RACKTRAY',
    'MODUL', 'MODULE', 'CIHAZ', 'KLAVYE', 'MONITOR', 'MONITÖR', 'TABLET',
    'KABLO', 'PATCH PANEL',
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

    Turkce karakterler icin cp1254 sart: veritabani Windows-1254 kullaniyor,
    varsayilan cozumleme "BÖLGE" yerine "B?LGE" uretir.
    """
    import pyodbc
    conn = pyodbc.connect(build_connection_string(get_logo_settings()))
    conn.setdecoding(pyodbc.SQL_CHAR, encoding='cp1254')
    conn.setdecoding(pyodbc.SQL_WCHAR, encoding='cp1254')
    return conn


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

    Gercek veriden ogrenilen kaliplar: "1YIL", "3 YILLIK", "3YEAR", "1 YEAR"
    ve bosluksuz yazimlar ("GUVLIC3Y", "FAORTIAUTH.3Y").
    """
    m = (urun_adi or '').upper()

    yil = re.search(r'(\d+)\s*(?:YIL|YEAR)', m)
    if yil:
        return int(yil.group(1)) * 12

    ay = re.search(r'(\d+)\s*(?:AY|MONTH)', m)
    if ay:
        return int(ay.group(1))

    # "3Y" — tek rakam + Y. Ardindan harf/rakam gelmemeli ki "WGT1850203"
    # gibi model kodlari ve "SU1YP-00" gibi SKU'lar yanlislikla eslesmesin.
    kisa = re.search(r'(?<!\d)(\d)Y(?![A-Z0-9])', m)
    if kisa:
        return int(kisa.group(1)) * 12

    return None


def _donanim_mi(urun_adi):
    m = (urun_adi or '').upper()
    return any(k in m for k in DONANIM_KELIMELERI)


def _kalici_lisans_mi(urun_adi):
    m = (urun_adi or '').upper()
    return any(k in m for k in KALICI_LISANS_KELIMELERI)


def _like_kosulu(markalar, alan='ITM.NAME'):
    return ' OR '.join(f"{alan} LIKE '%{k}%'" for k in markalar)


def _temiz_mail(deger):
    mail = (deger or '').strip()
    return '' if mail in ('-', '.', '_') else mail


def sync_logo_invoices(gecmis_yil=3):
    """Sureli lisans satislarini Logo'dan cekip yerel veritabanina yazar.

    Doner: (eklenen, sure_bekleyen, atlanan)
    """
    ayarlar = get_logo_settings()
    firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
    donem = (ayarlar.get('logo_period_no') or '01').zfill(2)

    conn = _baglan()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT INV.FICHENO, INV.DATE_, STL.LOGICALREF AS satir_ref,
               CLC.DEFINITION_ AS cari_ad, CLC.EMAILADDR AS cari_mail,
               CLC.CODE AS cari_kod, ITM.NAME AS urun_adi, ITM.CODE AS urun_kod
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

        ay = sure_ay_bul(urun)
        if ay:
            bitis = calculate_dates(satis_tarihi, ay)
            durum = 'PENDING'
            sure_tipi = {12: '1_YEAR', 24: '2_YEARS',
                         36: '3_YEARS', 60: '5_YEARS'}.get(ay, 'CUSTOM')
        else:
            # Sure bilinmiyor: bitis olarak satis tarihi konur ama
            # NEEDS_DURATION durumu hatirlatma uretilmesini engeller.
            ay, bitis = 0, satis_tarihi
            durum, sure_tipi = 'NEEDS_DURATION', 'CUSTOM'
            sure_bekleyen += 1

        yc.execute('''
            INSERT INTO sales (product_name, client_name, client_email, sales_rep,
                               license_key, sale_date, duration_type, duration_months,
                               expiration_date, reminder_type, status, notes,
                               logo_ref, source)
            VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, 'STAGED', ?, ?, ?, 'LOGO')
        ''', (urun, cari, mail, (r.urun_kod or '').strip(), satis_tarihi,
              sure_tipi, ay, bitis, durum,
              f"Logo faturası {r.FICHENO} (cari {r.cari_kod or '-'})", logo_ref))
        eklenen += 1

    yerel.commit()
    yerel.close()
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
        SELECT CLC.DEFINITION_ AS cari_ad, CLC.EMAILADDR AS cari_mail,
               ITM.NAME AS urun_adi,
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
        GROUP BY CLC.DEFINITION_, CLC.EMAILADDR, ITM.NAME
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

        if gecen > ortalama * risk_kat * 2:
            durum = 'LOST'
        elif gecen > ortalama * risk_kat:
            durum = 'AT_RISK'
            riskli += 1
        else:
            durum = 'ACTIVE'

        yc.execute('''
            INSERT INTO subscriptions
                (client_name, client_email, product_name, first_invoice_date,
                 last_invoice_date, invoice_count, avg_interval_days,
                 days_since_last, status, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'LOGO', CURRENT_TIMESTAMP)
            ON CONFLICT (client_name, product_name) DO UPDATE SET
                client_email = excluded.client_email,
                first_invoice_date = excluded.first_invoice_date,
                last_invoice_date = excluded.last_invoice_date,
                invoice_count = excluded.invoice_count,
                avg_interval_days = excluded.avg_interval_days,
                days_since_last = excluded.days_since_last,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
        ''', (cari, _temiz_mail(r.cari_mail), urun, ilk.isoformat(),
              son.isoformat(), adet, round(ortalama, 1), gecen, durum))
        yazilan += 1

    yerel.commit()
    yerel.close()
    return yazilan, riskli


if __name__ == '__main__':
    ok, mesaj = test_logo_connection()
    print(mesaj)
    if ok:
        e, s, a = sync_logo_invoices()
        print(f'Lisans : {e} eklendi ({s} süre bekliyor), {a} atlandı')
        y, r = sync_logo_subscriptions()
        print(f'Abonelik: {y} kayıt, {r} riskli')
