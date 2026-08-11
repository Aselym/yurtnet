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

    mode = settings.get('mode', 'MOCK').upper()
    recipients = get_internal_recipients(settings)
    recipient_email = ', '.join(recipients)
    recipient_name = f"Muhasebe & Satış Ekibi (İlgili müşteri: {sale_data.get('client_name', '')})"

    if not recipients:
        conn.close()
        return False, "İç bildirim alıcı listesi boş. Ayarlar sekmesinden muhasebe/satış e-postalarını ekleyin."

    if mode == 'MOCK':
        cursor.execute('''
            INSERT INTO sent_emails (sale_id, recipient_email, recipient_name, subject, body_html, reminder_stage, delivery_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            sale_data.get('id'),
            recipient_email,
            recipient_name,
            subject,
            body_html,
            reminder_stage,
            'MOCK'
        ))
        conn.commit()
        conn.close()
        return True, "E-posta sanal gelen kutusuna kaydedildi (Mock Modu)."

    elif mode == 'SMTP':
        try:
            smtp_host = settings.get('smtp_host', '')
            smtp_port = int(settings.get('smtp_port', 587))
            smtp_user = settings.get('smtp_user', '')
            smtp_password = settings.get('smtp_password', '')
            sender_email = settings.get('sender_email', smtp_user)
            sender_name = settings.get('sender_name', 'Lisans Hatırlatma Servisi')

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = recipient_email

            msg.attach(MIMEText(body_html, 'html', 'utf-8'))

            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(sender_email, recipients, msg.as_string())
            server.quit()

            cursor.execute('''
                INSERT INTO sent_emails (sale_id, recipient_email, recipient_name, subject, body_html, reminder_stage, delivery_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sale_data.get('id'),
                recipient_email,
                recipient_name,
                subject,
                body_html,
                reminder_stage,
                'SMTP'
            ))
            conn.commit()
            conn.close()
            return True, "E-posta SMTP sunucusu aracılığıyla başarıyla gönderildi."

        except Exception as e:
            conn.close()
            return False, f"SMTP Gönderim Hatası: {str(e)}"

    conn.close()
    return False, "Geçersiz e-posta modu."

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

    mode = settings.get('mode', 'MOCK').upper()
    recipients = get_internal_recipients(settings)
    recipient_email = ', '.join(recipients)
    recipient_name = f"Muhasebe & Satış Ekibi (İlgili müşteri: {invoice_data.get('client_name', '')})"

    if not recipients:
        conn.close()
        return False, "İç bildirim alıcı listesi boş. Ayarlar sekmesinden muhasebe/satış e-postalarını ekleyin."

    if mode == 'MOCK':
        cursor.execute('''
            INSERT INTO sent_emails (invoice_id, recipient_email, recipient_name, subject, body_html, reminder_stage, delivery_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            invoice_data.get('id'),
            recipient_email,
            recipient_name,
            subject,
            body_html,
            f'INVOICE_{stage}',
            'MOCK'
        ))
        conn.commit()
        conn.close()
        return True, "E-posta sanal gelen kutusuna kaydedildi (Mock Modu)."

    elif mode == 'SMTP':
        try:
            smtp_host = settings.get('smtp_host', '')
            smtp_port = int(settings.get('smtp_port', 587))
            smtp_user = settings.get('smtp_user', '')
            smtp_password = settings.get('smtp_password', '')
            sender_email = settings.get('sender_email', smtp_user)
            sender_name = settings.get('sender_name', 'Fatura Hatırlatma Servisi')

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{sender_email}>"
            msg['To'] = recipient_email
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))

            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(sender_email, recipients, msg.as_string())
            server.quit()

            cursor.execute('''
                INSERT INTO sent_emails (invoice_id, recipient_email, recipient_name, subject, body_html, reminder_stage, delivery_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                invoice_data.get('id'),
                recipient_email,
                recipient_name,
                subject,
                body_html,
                f'INVOICE_{stage}',
                'SMTP'
            ))
            conn.commit()
            conn.close()
            return True, "E-posta SMTP sunucusu aracılığıyla başarıyla gönderildi."

        except Exception as e:
            conn.close()
            return False, f"SMTP Gönderim Hatası: {str(e)}"

    conn.close()
    return False, "Geçersiz e-posta modu."
