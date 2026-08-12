import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_db_connection

def render_template(template_html, subject_template, sale_data):
    sale_date = datetime.strptime(sale_data['sale_date'], '%Y-%m-%d')
    exp_date = datetime.strptime(sale_data['expiration_date'], '%Y-%m-%d')
    days_left = (exp_date - datetime.now()).days

    placeholders = {
        '{musteri_adi}': sale_data.get('client_name') or 'Değerli Müşterimiz',
        '{urun_adi}': sale_data.get('product_name') or 'Lisanslı Ürün',
        '{lisans_anahtari}': sale_data.get('license_key') or 'Belirtilmedi',
        '{bitis_tarihi}': sale_data.get('expiration_date') or '',
        '{kalan_gun}': str(max(0, days_left)),
        '{satis_temsilcisi}': sale_data.get('sales_rep') or 'Müşteri Temsilcisi',
        '{satis_tarihi}': sale_data.get('sale_date') or ''
    }

    body = template_html
    subject = subject_template

    for key, val in placeholders.items():
        body = body.replace(key, val)
        subject = subject.replace(key, val)

    return subject, body

def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def get_internal_recipients(settings=None):
    if settings is None:
        settings = get_settings()
    raw = settings.get('internal_recipients', '') or ''
    return [e.strip() for e in raw.split(',') if e.strip()]

def smtp_gonder(settings, recipients, subject, body_html):
    """Tek bir SMTP gönderimi yapar. (başarılı_mı, mesaj) döner."""
    smtp_host = (settings.get('smtp_host') or '').strip()
    if not smtp_host:
        return False, "SMTP sunucu adresi girilmemiş. Ayarlar sekmesinden doldurun."

    try:
        smtp_port = int(settings.get('smtp_port') or 587)
        smtp_user = settings.get('smtp_user', '')
        smtp_password = settings.get('smtp_password', '')
        sender_email = settings.get('sender_email') or smtp_user
        sender_name = settings.get('sender_name') or 'Piramit Lisans Takip'

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = ', '.join(recipients)
        msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
        server.starttls()
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        return True, "E-posta gönderildi."

    except Exception as e:
        return False, f"SMTP hatası: {e}"

def _gonderim_kaydet(cursor, subject, body_html, recipients, recipient_name,
                     stage, sale_id=None, invoice_id=None):
    cursor.execute('''
        INSERT INTO sent_emails (sale_id, invoice_id, recipient_email, recipient_name,
                                 subject, body_html, reminder_stage, delivery_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'SMTP')
    ''', (sale_id, invoice_id, ', '.join(recipients), recipient_name, subject, body_html, stage))

def send_test_email(recipients=None):
    """Ayarların doğruluğunu kontrol etmek için örnek bir hatırlatma gönderir."""
    settings = get_settings()
    alicilar = recipients or get_internal_recipients(settings)
    if not alicilar:
        return False, "Alıcı yok. Önce iç bildirim adreslerini girin."

    zaman = datetime.now().strftime('%d.%m.%Y %H:%M')
    subject = "Test: Piramit Lisans Takip e-posta ayarları çalışıyor"
    body_html = f'''<div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;
     border:1px solid #e6e6e9;border-radius:12px;padding:24px;color:#1a1a1c">
  <h2 style="margin:0 0 6px;color:#f2691f;font-size:19px">Test e-postası</h2>
  <p style="margin:0 0 16px;color:#55555e;font-size:14px">
    Bu mesajı görüyorsanız SMTP ayarlarınız doğru çalışıyor. Lisans yenileme ve
    ödenmemiş fatura hatırlatmaları bu adrese ulaşacak.
  </p>
  <div style="background:#fafafa;border-left:3px solid #f2691f;padding:12px 14px;
       border-radius:6px;font-size:13px;color:#55555e">
    Gönderim zamanı: <strong style="color:#1a1a1c">{zaman}</strong><br>
    Sunucu: <strong style="color:#1a1a1c">{settings.get('smtp_host', '-')}</strong>
  </div>
  <p style="margin:16px 0 0;font-size:12px;color:#8b8b95">
    Piramit Lisans Takip — otomatik test mesajı
  </p>
</div>'''

    basarili, mesaj = smtp_gonder(settings, alicilar, subject, body_html)
    if basarili:
        conn = get_db_connection()
        cursor = conn.cursor()
        _gonderim_kaydet(cursor, subject, body_html, alicilar, 'Test alıcısı', 'TEST')
        conn.commit()
        conn.close()
        return True, f"Test e-postası gönderildi: {', '.join(alicilar)}"
    return False, mesaj

def send_reminder_email(sale_data, reminder_stage):
    conn = get_db_connection()
    cursor = conn.cursor()

    template_key = 'FINAL_REMINDER' if reminder_stage == 'FINAL_REMINDER' else 'FIRST_REMINDER'
    cursor.execute('SELECT subject, body_html FROM email_templates WHERE template_key = ?', (template_key,))
    template = cursor.fetchone()

    if not template:
        conn.close()
        return False, "E-posta şablonu bulunamadı."

    subject, body_html = render_template(template['body_html'], template['subject'], sale_data)
    settings = get_settings()
    recipients = get_internal_recipients(settings)

    if not recipients:
        conn.close()
        return False, "İç bildirim alıcı listesi boş. Ayarlar sekmesinden muhasebe/satış e-postalarını ekleyin."

    basarili, mesaj = smtp_gonder(settings, recipients, subject, body_html)
    if not basarili:
        conn.close()
        return False, mesaj

    _gonderim_kaydet(
        cursor, subject, body_html, recipients,
        f"Muhasebe & Satış Ekibi (İlgili müşteri: {sale_data.get('client_name', '')})",
        reminder_stage, sale_id=sale_data.get('id'),
    )
    conn.commit()
    conn.close()
    return True, "Hatırlatma e-postası gönderildi."

def render_invoice_template(template_html, subject_template, invoice_data):
    due_date = datetime.strptime(invoice_data['due_date'], '%Y-%m-%d')
    days_left = (due_date - datetime.now()).days

    placeholders = {
        '{musteri_adi}': invoice_data.get('client_name') or 'Değerli Müşterimiz',
        '{fatura_no}': invoice_data.get('invoice_no') or 'Belirtilmedi',
        '{tutar}': f"{invoice_data.get('amount', 0):,.2f}".replace(',', '.'),
        '{para_birimi}': invoice_data.get('currency') or 'TRY',
        '{vade_tarihi}': invoice_data.get('due_date') or '',
        '{kalan_gun}': str(max(0, days_left)),
    }

    body = template_html
    subject = subject_template
    for key, val in placeholders.items():
        body = body.replace(key, val)
        subject = subject.replace(key, val)

    return subject, body

INVOICE_STAGE_TEMPLATE_KEYS = {
    'WEEK': 'INVOICE_WEEK_REMINDER',
    'DAY': 'INVOICE_DAY_REMINDER',
    'OVERDUE': 'INVOICE_OVERDUE',
}

def send_invoice_reminder(invoice_data, stage):
    conn = get_db_connection()
    cursor = conn.cursor()

    template_key = INVOICE_STAGE_TEMPLATE_KEYS.get(stage, 'INVOICE_WEEK_REMINDER')
    cursor.execute('SELECT subject, body_html FROM email_templates WHERE template_key = ?', (template_key,))
    template = cursor.fetchone()

    if not template:
        conn.close()
        return False, "E-posta şablonu bulunamadı."

    subject, body_html = render_invoice_template(template['body_html'], template['subject'], invoice_data)
    settings = get_settings()
    recipients = get_internal_recipients(settings)

    if not recipients:
        conn.close()
        return False, "İç bildirim alıcı listesi boş. Ayarlar sekmesinden muhasebe/satış e-postalarını ekleyin."

    basarili, mesaj = smtp_gonder(settings, recipients, subject, body_html)
    if not basarili:
        conn.close()
        return False, mesaj

    _gonderim_kaydet(
        cursor, subject, body_html, recipients,
        f"Muhasebe & Satış Ekibi (İlgili müşteri: {invoice_data.get('client_name', '')})",
        f'INVOICE_{stage}', invoice_id=invoice_data.get('id'),
    )
    conn.commit()
    conn.close()
    return True, "Fatura hatırlatması gönderildi."
