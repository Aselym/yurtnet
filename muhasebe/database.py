import sqlite3
import json
import os
import hashlib
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'license_reminders.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
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
            status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'FIRST_REMINDER_SENT', 'FINAL_REMINDER_SENT', 'EXPIRED'
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
            reminder_stage TEXT NOT NULL, -- 'FIRST_REMINDER' (30 Days), 'FINAL_REMINDER' (7 Days), 'TEST'
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
    ]
    for key, val in default_settings:
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (key, val))

    conn.commit()
    conn.close()

def calculate_dates(sale_date_str, duration_months):
    sale_date = datetime.strptime(sale_date_str, '%Y-%m-%d')

    year = sale_date.year + (sale_date.month + duration_months - 1) // 12
    month = (sale_date.month + duration_months - 1) % 12 + 1
    day = min(sale_date.day, 28)
    
    expiration_date = datetime(year, month, day)
    return expiration_date.strftime('%Y-%m-%d')

def sure_dolmuslari_isaretle():
    """Bitis tarihi gecmis lisanslari EXPIRED yapar.

    Bu bir veri gercegi, mail gonderiminin yan etkisi degil — o yuzden
    zamanlayicidan ayri duruyor ve Logo senkronizasyonundan sonra da
    cagriliyor. NEEDS_DURATION olanlara dokunulmaz: onlarin bitis tarihi
    tahmini, uzerine "suresi doldu" demek yaniltici olur.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE sales SET status = 'EXPIRED'
        WHERE status NOT IN ('EXPIRED', 'NEEDS_DURATION')
          AND date(expiration_date) <= date('now')
    """)
    adet = cursor.rowcount
    conn.commit()
    conn.close()
    return adet


if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")
