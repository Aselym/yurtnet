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
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_key TEXT UNIQUE NOT NULL, -- 'FIRST_REMINDER', 'FINAL_REMINDER'
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            body_html TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    cursor.execute("PRAGMA table_info(sent_emails)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    if 'invoice_id' not in existing_cols:
        cursor.execute('ALTER TABLE sent_emails ADD COLUMN invoice_id INTEGER')

    default_templates = [
            (
                'FIRST_REMINDER',
                '1 Ay Kala Hatırlatma Şablonu (İlk Bildirim)',
                'Hatırlatma: {urun_adi} Lisansınızın Süresi 1 Ay İçinde Doluyor!',
                '''<div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #1e293b;">
    <h2 style="color: #38bdf8; margin-top: 0;">Muhasebe & Satış Ekibi,</h2>
    <p style="font-size: 13px; color: #94a3b8; margin-top: -8px;">İlgili müşteri: {musteri_adi}</p>
    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
        Şirketiniz adına kayıtlı olan <strong>{urun_adi}</strong> ürününüzün lisans süresi <strong>{bitis_tarihi}</strong> tarihinde sona erecektir.
    </p>
    <div style="background-color: #1e293b; border-left: 4px solid #38bdf8; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 4px 0; color: #94a3b8; font-size: 13px;">Lisans Bilgileri:</p>
        <p style="margin: 4px 0; color: #f8fafc; font-weight: bold;">Ürün: {urun_adi}</p>
        <p style="margin: 4px 0; color: #f8fafc;">Lisans Anahtarı: <code style="background:#0f172a; padding:2px 6px; border-radius:4px; color:#38bdf8;">{lisans_anahtari}</code></p>
        <p style="margin: 4px 0; color: #f8fafc;">Bitiş Tarihi: {bitis_tarihi} ({kalan_gun} gün kaldı)</p>
        <p style="margin: 4px 0; color: #f8fafc;">Satış Temsilcisi: {satis_temsilcisi}</p>
    </div>
    <p style="font-size: 14px; color: #94a3b8;">
        Hizmet kesintisi yaşamamak için lütfen satış temsilciniz ile iletişime geçiniz.
    </p>
    <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
    <p style="font-size: 12px; color: #64748b; text-align: center;">Bu e-posta Lisans Takip ve Otomatik Hatırlatma Sistemi tarafından otomatik gönderilmiştir.</p>
</div>'''
            ),
            (
                'FINAL_REMINDER',
                '1 Hafta Kala Hatırlatma Şablonu (Son Bildirim)',
                'ÖNEMLİ ACİL: {urun_adi} Lisansınızın Süresi 1 Hafta İçinde Doluyor!',
                '''<div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #ef4444;">
    <h2 style="color: #f87171; margin-top: 0;">Muhasebe & Satış Ekibi,</h2>
    <p style="font-size: 13px; color: #94a3b8; margin-top: -8px;">İlgili müşteri: {musteri_adi}</p>
    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
        <strong>{urun_adi}</strong> lisansınızın bitmesine sadece <span style="color: #f87171; font-weight: bold;">{kalan_gun} gün</span> kalmıştır!
    </p>
    <div style="background-color: #1e293b; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 4px 0; color: #94a3b8; font-size: 13px;">Detaylar:</p>
        <p style="margin: 4px 0; color: #f8fafc; font-weight: bold;">Ürün: {urun_adi}</p>
        <p style="margin: 4px 0; color: #f8fafc;">Lisans Anahtarı: <code style="background:#0f172a; padding:2px 6px; border-radius:4px; color:#f87171;">{lisans_anahtari}</code></p>
        <p style="margin: 4px 0; color: #f8fafc;">Son Kullanma Tarihi: <strong>{bitis_tarihi}</strong></p>
        <p style="margin: 4px 0; color: #f8fafc;">Satış Temsilciniz: {satis_temsilcisi}</p>
    </div>
    <p style="font-size: 14px; color: #fca5a5;">
        Lisans süreniz dolduğunda sistem erişiminiz durdurulabilir. Lütfen vakit kaybetmeden bizimle iletişime geçin.
    </p>
    <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
    <p style="font-size: 12px; color: #64748b; text-align: center;">Bu mesaj acil lisans sonlandırma uyarısıdır.</p>
</div>'''
            ),
            (
                'INVOICE_WEEK_REMINDER',
                'Fatura - 1 Hafta Kala Hatırlatma',
                'Hatırlatma: {fatura_no} Numaralı Faturanızın Vadesi Yaklaşıyor',
                '''<div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #1e293b;">
    <h2 style="color: #38bdf8; margin-top: 0;">Muhasebe & Satış Ekibi,</h2>
    <p style="font-size: 13px; color: #94a3b8; margin-top: -8px;">İlgili müşteri: {musteri_adi}</p>
    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
        <strong>{fatura_no}</strong> numaralı faturanızın vade tarihi <strong>{vade_tarihi}</strong> olup, ödemenize <strong>{kalan_gun} gün</strong> kalmıştır.
    </p>
    <div style="background-color: #1e293b; border-left: 4px solid #38bdf8; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 4px 0; color: #f8fafc; font-weight: bold;">Tutar: {tutar} {para_birimi}</p>
        <p style="margin: 4px 0; color: #f8fafc;">Vade Tarihi: {vade_tarihi}</p>
    </div>
    <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
    <p style="font-size: 12px; color: #64748b; text-align: center;">Bu e-posta Fatura Takip ve Otomatik Hatırlatma Sistemi tarafından otomatik gönderilmiştir.</p>
</div>'''
            ),
            (
                'INVOICE_DAY_REMINDER',
                'Fatura - 1 Gün Kala Son Hatırlatma',
                'ÖNEMLİ: {fatura_no} Numaralı Faturanızın Vadesi Yarın Doluyor',
                '''<div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #ef4444;">
    <h2 style="color: #f87171; margin-top: 0;">Muhasebe & Satış Ekibi,</h2>
    <p style="font-size: 13px; color: #94a3b8; margin-top: -8px;">İlgili müşteri: {musteri_adi}</p>
    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
        <strong>{fatura_no}</strong> numaralı faturanızın vadesine sadece <span style="color: #f87171; font-weight: bold;">{kalan_gun} gün</span> kalmıştır!
    </p>
    <div style="background-color: #1e293b; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 4px 0; color: #f8fafc; font-weight: bold;">Tutar: {tutar} {para_birimi}</p>
        <p style="margin: 4px 0; color: #f8fafc;">Vade Tarihi: {vade_tarihi}</p>
    </div>
    <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
    <p style="font-size: 12px; color: #64748b; text-align: center;">Bu mesaj acil ödeme vadesi uyarısıdır.</p>
</div>'''
            ),
            (
                'INVOICE_OVERDUE',
                'Fatura - Vadesi Geçmiş Uyarı',
                'GECİKME: {fatura_no} Numaralı Faturanızın Vadesi Geçti',
                '''<div style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px; max-width: 600px; margin: 0 auto; border: 1px solid #ef4444;">
    <h2 style="color: #f87171; margin-top: 0;">Muhasebe & Satış Ekibi,</h2>
    <p style="font-size: 13px; color: #94a3b8; margin-top: -8px;">İlgili müşteri: {musteri_adi}</p>
    <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
        <strong>{fatura_no}</strong> numaralı, <strong>{vade_tarihi}</strong> vade tarihli faturanızın ödemesi henüz alınmamıştır.
    </p>
    <div style="background-color: #1e293b; border-left: 4px solid #ef4444; padding: 16px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 4px 0; color: #f8fafc; font-weight: bold;">Tutar: {tutar} {para_birimi}</p>
        <p style="margin: 4px 0; color: #f8fafc;">Vade Tarihi: {vade_tarihi}</p>
    </div>
    <p style="font-size: 14px; color: #fca5a5;">Lütfen en kısa sürede ödemenizi gerçekleştiriniz ya da muhasebe departmanımızla iletişime geçiniz.</p>
    <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
    <p style="font-size: 12px; color: #64748b; text-align: center;">Bu mesaj vadesi geçmiş fatura uyarısıdır.</p>
</div>'''
            )
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO email_templates (template_key, title, subject, body_html)
        VALUES (?, ?, ?, ?)
    ''', default_templates)

    default_admin_salt, default_admin_hash = hash_password('Aa123456')
    default_settings = [
        ('mode', 'MOCK'), # 'MOCK' or 'SMTP'
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

    cursor.execute('SELECT COUNT(*) FROM sales')
    if cursor.fetchone()[0] == 0:
        sample_sales = [
            (
                'Müşteri A - WatchGuard T125 3 Yıllık Güvenlik Lisansı',
                'Müşteri A Teknoloji A.Ş.',
                'bilgi@musteria.com',
                'Ahmet Yılmaz',
                'WG-9842-X78A-3321',
                '2023-08-14',
                '3_YEARS',
                36,
                '2026-08-14',
                'STAGED',
                'PENDING',
                'Firewall cihazı ile birlikte 3 yıllık paket satıldı.'
            ),
            (
                'ABC Holding - Microsoft 365 Business Premium (50 Kullanıcı)',
                'ABC Holding A.Ş.',
                'it@abcholding.com.tr',
                'Zeynep Demir',
                'MS-365-BP-50U-2025',
                '2025-09-01',
                '1_YEAR',
                12,
                '2026-09-01',
                'STAGED',
                'PENDING',
                'Yıllık bulut lisansı aboneliği.'
            ),
            (
                'XYZ Lojistik - FortiGate 60F 5 Yıllık UTM Lisansı',
                'XYZ Lojistik Ltd. Şti.',
                'satin-alma@xyzlojistik.com',
                'Mehmet Kaya',
                'FG-60F-UTM-5Y-8841',
                '2024-01-15',
                '5_YEARS',
                60,
                '2029-01-15',
                '1_MONTH',
                'PENDING',
                '5 yıllık tam koruma paketi.'
            ),
            (
                'Teknoloji Ltd - Windows Server 2022 Datacenter 2 Yıllık Core',
                'Teknoloji Bilişim Ltd.',
                'destek@teknolojibilisim.com',
                'Ahmet Yılmaz',
                'WS-2022-DC-16C-9912',
                '2024-05-10',
                '2_YEARS',
                24,
                '2026-05-10',
                '1_WEEK',
                'EXPIRED',
                'Süresi dolmuş eski sunucu lisansı.'
            )
        ]
        cursor.executemany('''
            INSERT INTO sales (product_name, client_name, client_email, sales_rep, license_key, sale_date, duration_type, duration_months, expiration_date, reminder_type, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_sales)

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
