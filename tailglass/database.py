import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime

# MUHASEBE_DB ortam degiskeni ayri bir veritabaniyla calismayi saglar: demo/
# gelistirme verisi gercek license_reminders.db'ye (canli kayitlar, satis
# ekibinin yenileme kararlari) asla karismasin diye.
DB_PATH = os.environ.get('MUHASEBE_DB') or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'license_reminders.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100_000).hex()
    return salt, pwd_hash

def verify_password(password, salt, expected_hash):
    _, computed = hash_password(password, salt)
    return secrets.compare_digest(computed, expected_hash or '')

def init_db():
    conn = get_db_connection()
    # WAL: senkron yazarken arayuz okumaya devam edebilsin
    conn.execute('PRAGMA journal_mode=WAL')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            client_name TEXT NOT NULL,
            client_email TEXT NOT NULL,
            sales_rep TEXT,
            license_key TEXT,
            sale_date TEXT NOT NULL,
            duration_type TEXT NOT NULL, -- '1_YEAR', '2_YEARS', '3_YEARS', '5_YEARS', 'CUSTOM'
            duration_months INTEGER NOT NULL,
            expiration_date TEXT NOT NULL,
            reminder_type TEXT NOT NULL, -- '1_WEEK', '1_MONTH', 'STAGED'
            status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'FIRST_REMINDER_SENT', 'SECOND_REMINDER_SENT', 'FINAL_REMINDER_SENT', 'EXPIRED'
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            recipient_email TEXT NOT NULL,
            recipient_name TEXT,
            subject TEXT NOT NULL,
            body_html TEXT NOT NULL,
            reminder_stage TEXT NOT NULL, -- 'FIRST_REMINDER' (10 gun), 'SECOND_REMINDER' (5 gun), 'FINAL_REMINDER' (1 gun), 'TEST'
            delivery_mode TEXT NOT NULL, -- 'MOCK' or 'SMTP'
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sale_id) REFERENCES sales (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')


    # Microsoft CSP / Azure gibi aylik faturalanan abonelikler. Bunlarin
    # "suresi dolmuyor"; takip mantigi farkli: fatura kesilmeyi birakmissa
    # musteri abonelikten cikmis olabilir.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT NOT NULL,
            client_email TEXT,
            product_name TEXT NOT NULL,
            first_invoice_date TEXT NOT NULL,
            last_invoice_date TEXT NOT NULL,
            invoice_count INTEGER NOT NULL DEFAULT 1,
            avg_interval_days REAL,
            days_since_last INTEGER,
            status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE','AT_RISK','LOST'
            source TEXT DEFAULT 'LOGO',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (client_name, product_name)
        )
    ''')

    # Lisans ve abonelik disindaki her sey: bilgisayar, mouse, monitor, kablo...
    # Yenileme takibi yok; amac "bu musteriye ne satmisiz" sorusuna cevap vermek.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            product_code TEXT,
            client_name TEXT NOT NULL,
            client_email TEXT,
            quantity REAL NOT NULL DEFAULT 1,
            unit_price REAL,
            line_total REAL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            sale_date TEXT NOT NULL,
            invoice_no TEXT,
            logo_ref TEXT UNIQUE,
            source TEXT DEFAULT 'LOGO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Satis ekibinin Gmail uzerinden yaptigi teklifler. Logo'da izi olmadigi
    # icin elle giriliyor; lisans/fatura kayitlariyla karismasin diye ayri
    # tabloda duruyor ve yalnizca Teklifler sayfasinda listeleniyor.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            client_name TEXT NOT NULL,
            offer_price REAL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            offer_date TEXT NOT NULL,
            sales_rep TEXT,
            -- PENDING = geri donmedi (varsayilan), ACCEPTED = kabul, REJECTED = ret
            status TEXT NOT NULL DEFAULT 'PENDING',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute("PRAGMA table_info(sent_emails)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if 'invoice_id' not in existing_cols:
        cursor.execute('ALTER TABLE sent_emails ADD COLUMN invoice_id INTEGER')

    # Logo'dan gelen kayitlari tekilleştirmek icin: fatura no + urun
    cursor.execute("PRAGMA table_info(sales)")
    sales_cols = {row[1] for row in cursor.fetchall()}
    if 'logo_ref' not in sales_cols:
        cursor.execute('ALTER TABLE sales ADD COLUMN logo_ref TEXT')
    if 'source' not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN source TEXT DEFAULT 'MANUAL'")
    # Suresi dolmus bir lisansin yerine yenisi alinmis olabilir. Otomatik
    # kapatilmaz: urun kodlari degistigi icin eslesme yanilabilir, o yuzden
    # aday olarak isaretlenip satis ekibinin onayina birakilir.
    if 'renewed_by' not in sales_cols:
        cursor.execute('ALTER TABLE sales ADD COLUMN renewed_by INTEGER')
    if 'renewal_state' not in sales_cols:
        # NULL | 'SUSPECT' (aday) | 'CONFIRMED' (onaylandi) | 'REJECTED' (degil)
        cursor.execute('ALTER TABLE sales ADD COLUMN renewal_state TEXT')
    if 'price' not in sales_cols:
        # Logo'daki STLINE.TOTAL (satir tutari, TRY). NULL = fiyat bilinmiyor.
        cursor.execute('ALTER TABLE sales ADD COLUMN price REAL')
    if 'client_phone' not in sales_cols:
        # Logo'daki CLCARD.TELNRS1 (sabit telefon). Cep telefonu alani
        # (CELLPHONE) firma tarafindan hic kullanilmamis, o yuzden cekilmiyor.
        cursor.execute('ALTER TABLE sales ADD COLUMN client_phone TEXT')
    if 'client_city' not in sales_cols:
        cursor.execute('ALTER TABLE sales ADD COLUMN client_city TEXT')
    if 'reminders_sent_count' not in sales_cols:
        # Hatirlatma asamalari artik ayarlanabilir (10,5,1 sabit degil) —
        # kac asama gonderildigi sayi olarak tutuluyor. Eski durumlardan tasinir.
        cursor.execute('ALTER TABLE sales ADD COLUMN reminders_sent_count INTEGER DEFAULT 0')
        cursor.execute("""UPDATE sales SET reminders_sent_count = CASE status
                            WHEN 'FIRST_REMINDER_SENT' THEN 1 WHEN 'SECOND_REMINDER_SENT' THEN 2
                            WHEN 'FINAL_REMINDER_SENT' THEN 3 ELSE 0 END""")

    cursor.execute("PRAGMA table_info(products)")
    products_cols = {row[1] for row in cursor.fetchall()}
    if 'client_phone' not in products_cols:
        cursor.execute('ALTER TABLE products ADD COLUMN client_phone TEXT')
    if 'client_city' not in products_cols:
        cursor.execute('ALTER TABLE products ADD COLUMN client_city TEXT')

    cursor.execute("PRAGMA table_info(subscriptions)")
    subscriptions_cols = {row[1] for row in cursor.fetchall()}
    if 'client_phone' not in subscriptions_cols:
        cursor.execute('ALTER TABLE subscriptions ADD COLUMN client_phone TEXT')
    if 'client_city' not in subscriptions_cols:
        cursor.execute('ALTER TABLE subscriptions ADD COLUMN client_city TEXT')

    _ambar_semasi(cursor)

    default_admin_salt, default_admin_hash = hash_password('Aa123456')
    default_settings = [
        ('smtp_host', 'smtp.office365.com'),
        ('smtp_port', '587'),
        ('smtp_user', 'lisans@sirketiniz.com'),
        ('smtp_password', ''),
        ('sender_email', 'lisans@sirketiniz.com'),
        ('sender_name', 'Lisans Hatırlatma Servisi'),
        ('internal_recipients', ''),
        ('logo_sql_server', '127.0.0.1'),
        ('logo_sql_port', '1433'),
        ('logo_sql_db', 'LOGO_DB'),
        ('logo_sql_user', 'sa'),
        ('logo_sql_pass', ''),
        ('logo_firm_no', '001'),
        ('logo_period_no', '01'),
        ('logo_auto_sync', 'OFF'),
        ('admin_user', 'admin'),
        ('admin_pass_salt', default_admin_salt),
        ('admin_pass_hash', default_admin_hash),
        # --- kullanici kontrolundeki esikler (sabit sayi yok, hepsi Ayarlar'dan)
        ('logo_source', 'demo'),          # 'mssql' (gercek Logo) | 'demo'
        ('demo_db_path', ''),
        ('data_start_date', ''),           # bos = Logo'daki tum gecmis
        ('license_min_expiry', '2026-01-01'),
        ('reminder_days', '10,5,1'),
        ('expiring_soon_days', '90'),
        ('sub_min_invoices', '4'),
        ('sub_max_interval_days', '60'),
        ('sub_risk_factor', '2.0'),
        ('app_public_url', ''),
        ('company_name', ''),
        ('pinned_brands', ''),         # Urunler ve stok'ta sabit sekme (Dell partneri)
        ('company_logo', ''),              # data URL; Ayarlar > Sirket'ten yuklenir
        ('company_logo_dark', ''),
        ('base_currency', 'TRY'),
        ('sync_hours', '11,15,17'),
        ('tcmb_rates', 'ON'),              # dosya/e-Fatura kaynaginda eksik kurlar TCMB'den
        ('ai_provider', 'kapali'),         # kapali | groq | anthropic | ollama | openai
        ('ai_model', ''),                  # bos = saglayicinin varsayilani
        ('ai_api_key', ''),
        ('ai_base_url', ''),
        ('ai_instructions', ''),           # kullanicinin asistana ek talimatlari
        ('ai_db_access', 'ON'),            # asistan salt okunur araclarla toplu veri sorgulayabilir
    ]
    for key, val in default_settings:
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))
    _sirket_logosu_tasi(cursor)

    conn.commit()
    conn.close()

def _ambar_semasi(cursor):
    """Logo'dan satir bazinda alinan veri ambari.

    Tum analizler (pivot, donem raporu, stok, gelir kirilimlari) bu
    tablolardan, kullanicinin sectigi filtrelerle anlik hesaplanir; Logo'ya
    her ekran acilisinda sorgu atilmaz.
    """
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS wh_items (
            item_ref INTEGER PRIMARY KEY,
            code TEXT, name TEXT NOT NULL,
            logo_brand TEXT, logo_group TEXT,
            brand TEXT, brand_src TEXT,          -- 'kural' | 'logo' | 'sozluk' | 'tahmin'
            category TEXT, category_src TEXT,
            kind TEXT,                           -- 'urun' | 'lisans' | 'abonelik' | 'kalici'
            revenue_type TEXT,                   -- 'Ürün' | 'Tekrarlayan'
            duration_months INTEGER
        );
        CREATE TABLE IF NOT EXISTS wh_clients (
            client_ref INTEGER PRIMARY KEY,
            code TEXT, name TEXT NOT NULL, cardtype INTEGER,
            email TEXT, phone TEXT, city TEXT
        );
        CREATE TABLE IF NOT EXISTS wh_salesmen (
            salesman_ref INTEGER PRIMARY KEY, code TEXT, name TEXT
        );
        CREATE TABLE IF NOT EXISTS wh_lines (
            line_ref INTEGER NOT NULL,
            period TEXT NOT NULL DEFAULT '01',
            inv_ref INTEGER, fiche_no TEXT, date TEXT NOT NULL,
            trcode INTEGER, iocode INTEGER, linetype INTEGER,
            direction TEXT NOT NULL,             -- SATIS | ALIS | SATIS_IADE | ALIS_IADE | DIGER
            client_ref INTEGER, item_ref INTEGER, salesman_ref INTEGER,
            qty REAL, price_tl REAL, gross_tl REAL, net_tl REAL,
            rate REAL, net_usd REAL,
            cancelled INTEGER NOT NULL DEFAULT 0,
            -- FIFO ile hesaplanan tahmini maliyet ve alis tarihi
            cost_tl REAL, cost_usd REAL, cost_date TEXT, cost_complete INTEGER,
            PRIMARY KEY (period, line_ref)
        );
        CREATE INDEX IF NOT EXISTS ix_wh_lines_date ON wh_lines(date);
        CREATE INDEX IF NOT EXISTS ix_wh_lines_item ON wh_lines(item_ref, date);
        CREATE INDEX IF NOT EXISTS ix_wh_lines_client ON wh_lines(client_ref, date);
        CREATE INDEX IF NOT EXISTS ix_wh_lines_dir ON wh_lines(direction, date);

        -- Kullanicinin siniflandirma kurallari: urun adinda/kodunda gecen
        -- kelimeye gore marka, kategori ya da gelir tipi atar. Logo'daki
        -- marka/grup alanlarindan ve yerlesik sozlukten ONCE uygulanir.
        CREATE TABLE IF NOT EXISTS class_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            field TEXT NOT NULL,                 -- 'brand' | 'category' | 'revenue_type'
            pattern TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Bagli firmalar: ana firma + yan firmalar ayni grup adinda toplanir.
        -- Abonelik sagligi gruba gore hesaplanir (fatura bazen yan firmaya
        -- kesiliyor) ve analizlerde "Firma grubu" kirilimi olarak kullanilir.
        CREATE TABLE IF NOT EXISTS client_groups (
            client_name TEXT PRIMARY KEY,
            group_name TEXT NOT NULL
        );

        -- Kullanicinin kaydettigi analiz gorunumleri (pivot ayarlari)
        CREATE TABLE IF NOT EXISTS saved_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            page TEXT NOT NULL,
            config TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT, finished_at TEXT, source TEXT,
            ok INTEGER, lines INTEGER, items INTEGER, clients INTEGER,
            message TEXT
        );
    ''')


def get_setting(key, default=None):
    conn = get_db_connection()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row['value'] if row and row['value'] not in (None, '') else default


def get_settings():
    conn = get_db_connection()
    rows = conn.execute('SELECT key, value FROM settings').fetchall()
    conn.close()
    return {r['key']: r['value'] for r in rows}


def setting_float(ayarlar, key, default):
    try:
        return float(ayarlar.get(key) or default)
    except (TypeError, ValueError):
        return default


def setting_int_list(ayarlar, key, default):
    try:
        return sorted({int(x) for x in (ayarlar.get(key) or default).split(',') if x.strip()}, reverse=True)
    except ValueError:
        return sorted({int(x) for x in default.split(',')}, reverse=True)


def calculate_dates(sale_date_str, duration_months):
    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d')

    year = sale_date.year + (sale_date.month + duration_months - 1) // 12
    month = (sale_date.month + duration_months - 1) % 12 + 1
    day = min(sale_date.day, 28)
    
    expiration_date = datetime(year, month, day)
    return expiration_date.strftime('%Y-%m-%d')

def _sirket_logosu_tasi(cursor):
    """Urun adi artik sabit (Tailglass Analytics); eski kurulumlarin
    static/images altindaki sirket logosu bir kez ayara tasinir, boylece logo
    arayuz derlemesinden bagimsiz olur ve Ayarlar'dan degistirilebilir."""
    import base64
    gorseller = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'images')
    for anahtar, dosya in (('company_logo', 'logo.png'), ('company_logo_dark', 'logo-dark.png')):
        mevcut = cursor.execute('SELECT value FROM settings WHERE key = ?', (anahtar,)).fetchone()
        yol = os.path.join(gorseller, dosya)
        if mevcut and not mevcut[0] and os.path.exists(yol) and os.path.getsize(yol) < 300 * 1024:
            veri = 'data:image/png;base64,' + base64.b64encode(open(yol, 'rb').read()).decode('ascii')
            cursor.execute('UPDATE settings SET value = ? WHERE key = ?', (veri, anahtar))


def sure_dolmuslari_isaretle():
    """Bitis tarihi gecmis lisanslari EXPIRED yapar.

    Bu bir veri gercegi, mail gonderiminin yan etkisi degil — o yuzden
    zamanlayicidan ayri duruyor ve Logo senkronizasyonundan sonra da
    cagriliyor. NEEDS_DURATION olanlara dokunulmaz: onlarin bitis tarihi
    tahmini, uzerine "suresi doldu" demek yaniltici olur. RENEWED olanlara
    da dokunulmaz: bu kayitlarin bitis tarihi zaten gecmiste (yenilenmeden
    once son kullanma tarihiydi), dokunulmazsa her 5 dakikada bir calisan
    zamanlayici bunlari sessizce tekrar EXPIRED'a cevirip onay/otomatik-
    yenileme isaretini kaybettiriyordu.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sales SET status = 'EXPIRED'
        WHERE status NOT IN ('EXPIRED', 'NEEDS_DURATION', 'RENEWED')
          AND date(expiration_date) <= date('now')
    """)
    adet = cursor.rowcount
    conn.commit()
    conn.close()
    return adet


if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")
