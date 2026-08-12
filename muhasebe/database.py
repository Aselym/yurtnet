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

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT,
            client_name TEXT NOT NULL,
            client_email TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'TRY',
            issue_date TEXT NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'UNPAID', -- 'UNPAID', 'PAID'
            reminder_stage TEXT NOT NULL DEFAULT 'NONE', -- 'NONE','WEEK_SENT','DAY_SENT','OVERDUE_SENT'
            source TEXT DEFAULT 'MANUAL', -- 'MANUAL','LOGO'
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

if __name__ == '__main__':
    init_db()
    print("Database initialised successfully.")
