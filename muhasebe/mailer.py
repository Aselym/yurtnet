import html
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_db_connection

MARKA = '#f2691f'
METIN = '#1a1a1c'
SOLUK = '#55555e'
CIZGI = '#e6e6e9'

# Ürün adından tür çıkarımı — mailde doğal bir cümle kurmak için.
URUN_TURLERI = [
    (('WATCHGUARD', 'WATCGUARD', 'FORTIGATE', 'FORTINET', 'SOPHOS'),
     'güvenlik duvarı lisansı'),
    (('EPDR', 'ENDPOINT', 'ESET', 'KASPERSKY', 'ANTIVIR'),
     'uç nokta güvenlik lisansı'),
    (('VEEAM', 'BACKUP', 'YEDEK'),
     'yedekleme lisansı'),
    (('5651', 'PLOG', 'SIGNLOGGER', 'CRYPTTECH', 'LOGLAMA'),
     '5651 loglama lisansı'),
    (('AUTHPOINT', 'MFA', 'AUTHENTIC'),
     'çok faktörlü kimlik doğrulama lisansı'),
    (('MICROSOFT', 'AZURE', 'CSP', 'M365', '365'),
     'Microsoft aboneliği'),
]


def urun_turu(urun_adi):
    m = (urun_adi or '').upper()
    for kelimeler, tur in URUN_TURLERI:
        if any(k in m for k in kelimeler):
            return tur
    return 'lisansı'


def _gun_ifadesi(kalan_gun):
    """Kalan güne göre hem aciliyet rengi hem insan diliyle süre ifadesi."""
    if kalan_gun < 0:
        return f'{abs(kalan_gun)} gün önce doldu', '#b3261e', 'GECİKMİŞ'
    if kalan_gun == 0:
        return 'bugün doluyor', '#b3261e', 'BUGÜN'
    if kalan_gun == 1:
        return 'yarın doluyor', '#b3261e', 'ACİL'
    if kalan_gun <= 7:
        return f'{kalan_gun} gün sonra doluyor', '#a45c00', 'ACİL'
    return f'{kalan_gun} gün sonra doluyor', MARKA, 'HATIRLATMA'


def lisans_maili(sale_data):
    """Satış ekibine gidecek yenileme hatırlatmasını üretir.

    Şablon veritabanında tutulmuyor; metin müşteri ve ürün bilgisine göre
    burada kuruluyor, böylece her ürün için doğru dilde cümle çıkıyor.
    """
    musteri = sale_data.get('client_name') or 'Müşteri'
    urun = sale_data.get('product_name') or 'Lisanslı ürün'
    bitis = sale_data.get('expiration_date') or ''
    temsilci = (sale_data.get('sales_rep') or '').strip()
    anahtar = (sale_data.get('license_key') or '').strip()

    try:
        kalan = (datetime.strptime(bitis, '%Y-%m-%d') - datetime.now()).days
    except ValueError:
        kalan = 0

    sure_ifadesi, renk, etiket = _gun_ifadesi(kalan)
    tur = urun_turu(urun)

    subject = f'[{etiket}] {musteri} — {tur} {sure_ifadesi}'

    # Bu degerler Logo'dan geliyor (musteri/urun kartlari staff tarafindan
    # elle giriliyor) — HTML maile basmadan once kacirilmazsa, iceride
    # yanlislikla ya da kotu niyetle "<" gibi bir karakter geçen bir kayit
    # alici mail istemcisinde HTML olarak yorumlanabilir.
    satirlar = [
        ('Müşteri', html.escape(musteri)),
        ('Ürün', html.escape(urun)),
        ('Bitiş tarihi', html.escape(bitis)),
    ]
    if anahtar:
        satirlar.append(('Lisans anahtarı', html.escape(anahtar)))
    if temsilci:
        satirlar.append(('Satış temsilcisi', html.escape(temsilci)))

    detay = ''.join(
        f'<tr>'
        f'<td style="padding:7px 0;color:{SOLUK};font-size:13px;width:140px;'
        f'vertical-align:top">{etiket_}</td>'
        f'<td style="padding:7px 0;color:{METIN};font-size:14px;font-weight:600">'
        f'{deger}</td></tr>'
        for etiket_, deger in satirlar
    )

    if kalan < 0:
        eylem = ('Lisans süresi dolmuş durumda. Müşteri hâlâ kullanıyorsa koruma '
                 'devre dışı kalmış olabilir — yenileme için bir an önce iletişime geçin.')
    elif kalan <= 7:
        eylem = ('Yenileme teklifinin bu hafta içinde iletilmesi gerekiyor, '
                 'aksi halde müşteri korumasız kalacak.')
    else:
        eylem = 'Yenileme teklifi hazırlamak için uygun zaman.'

    body = f'''<div style="font-family:'Segoe UI',system-ui,sans-serif;max-width:560px;
     margin:0 auto;color:{METIN};line-height:1.55">
  <div style="border:1px solid {CIZGI};border-radius:12px;overflow:hidden">
    <div style="background:{renk};padding:14px 22px">
      <span style="color:#fff;font-size:12px;font-weight:700;letter-spacing:.08em">
        {etiket}
      </span>
    </div>
    <div style="padding:22px">
      <p style="margin:0 0 18px;font-size:15px">
        <strong>{html.escape(musteri)}</strong> firmasına satılan {tur}
        <strong style="color:{renk}">{sure_ifadesi}</strong>.
      </p>
      <table style="width:100%;border-collapse:collapse;border-top:1px solid {CIZGI};
             border-bottom:1px solid {CIZGI}">{detay}</table>
      <p style="margin:18px 0 0;font-size:14px;color:{SOLUK}">{eylem}</p>
    </div>
  </div>
  <p style="margin:14px 0 0;font-size:11px;color:#8b8b95;text-align:center">
    Piramit Lisans Takip — otomatik hatırlatma
  </p>
</div>'''

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
                     stage, sale_id=None):
    cursor.execute('''
        INSERT INTO sent_emails (sale_id, recipient_email, recipient_name,
                                 subject, body_html, reminder_stage, delivery_mode)
        VALUES (?, ?, ?, ?, ?, ?, 'SMTP')
    ''', (sale_id, ', '.join(recipients), recipient_name, subject, body_html, stage))

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
    Bu mesajı görüyorsanız SMTP ayarlarınız doğru çalışıyor. Lisans yenileme hatırlatmaları bu adrese ulaşacak.
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

    subject, body_html = lisans_maili(sale_data)
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
