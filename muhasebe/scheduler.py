import os
import shutil
import threading
import time
from datetime import datetime
from database import DB_PATH, get_db_connection, sure_dolmuslari_isaretle
from logo_sync import sync_logo_invoices, sync_logo_subscriptions, sync_logo_products, yenileme_adaylari_bul, get_logo_settings
from mailer import send_reminder_email
from notifier import send_windows_toast

# Logo'dan otomatik veri cekme saatleri. Muhasebe/satis ekibinin gun icinde
# baktigi saatlerle hizali: ogleden once, ogleden sonra, aksam kapanistan once.
LOGO_SYNC_SAATLERI = (11, 15, 17)

# license_reminders.db Logo'dan cekilemeyen veriyi de tutuyor (teklifler,
# hatirlatma gecmisi, yenileme kararlari) — hicbir yere yedeklenmiyordu.
# Gece, kullanim olmayan bir saatte gunluk yedek alinir.
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
BACKUP_SAATI = 4
BACKUP_TUTULACAK_ADET = 14

def check_and_send_reminders():
    sure_dolmuslari_isaretle()

    conn = get_db_connection()
    cursor = conn.cursor()

    # NEEDS_DURATION: suresi bilinmeyen kayitlar. Bitis tarihi tahmin olacagi
    # icin hatirlatma uretilmez; once elle sure girilmeli.
    # duration_months = 0 kontrolu ikinci bir emniyet: durum alani baska bir
    # yerde yanlislikla degistirilse bile suresi girilmemis kayit islenmez.
    cursor.execute("""
        SELECT * FROM sales
        WHERE status NOT IN ('EXPIRED', 'NEEDS_DURATION')
          AND COALESCE(duration_months, 0) > 0
    """)
    sales = [dict(row) for row in cursor.fetchall()]

    today = datetime.now().date()
    sent_count = 0

    for sale in sales:
        exp_date = datetime.strptime(sale['expiration_date'], '%Y-%m-%d').date()
        days_left = (exp_date - today).days
        status = sale['status']
        reminder_type = sale['reminder_type']
        sale_id = sale['id']

        if days_left <= 0:
            cursor.execute('UPDATE sales SET status = "EXPIRED" WHERE id = ?', (sale_id,))
            conn.commit()
            continue

        if reminder_type == '1_WEEK':
            if days_left <= 7 and status == 'PENDING':
                success, msg = send_reminder_email(sale, 'FINAL_REMINDER')
                if success:
                    cursor.execute('UPDATE sales SET status = "FINAL_REMINDER_SENT" WHERE id = ?', (sale_id,))
                    conn.commit()
                    sent_count += 1
                    send_windows_toast("Lisans Süresi Yaklaşıyor", f"{sale['client_name']} - {sale['product_name']} ({days_left} gün kaldı)")

        elif reminder_type == '1_MONTH':
            if days_left <= 30 and status == 'PENDING':
                success, msg = send_reminder_email(sale, 'FIRST_REMINDER')
                if success:
                    cursor.execute('UPDATE sales SET status = "FIRST_REMINDER_SENT" WHERE id = ?', (sale_id,))
                    conn.commit()
                    sent_count += 1
                    send_windows_toast("Lisans Süresi Yaklaşıyor", f"{sale['client_name']} - {sale['product_name']} ({days_left} gün kaldı)")

        elif reminder_type == 'STAGED':
            if 7 < days_left <= 30 and status == 'PENDING':
                success, msg = send_reminder_email(sale, 'FIRST_REMINDER')
                if success:
                    cursor.execute('UPDATE sales SET status = "FIRST_REMINDER_SENT" WHERE id = ?', (sale_id,))
                    conn.commit()
                    sent_count += 1
                    send_windows_toast("Lisans Süresi Yaklaşıyor", f"{sale['client_name']} - {sale['product_name']} ({days_left} gün kaldı)")

            elif days_left <= 7 and status in ('PENDING', 'FIRST_REMINDER_SENT'):
                success, msg = send_reminder_email(sale, 'FINAL_REMINDER')
                if success:
                    cursor.execute('UPDATE sales SET status = "FINAL_REMINDER_SENT" WHERE id = ?', (sale_id,))
                    conn.commit()
                    sent_count += 1
                    send_windows_toast("Lisans Süresi Yaklaşıyor", f"{sale['client_name']} - {sale['product_name']} ({days_left} gün kaldı)")

    conn.close()
    return sent_count

def scheduler_loop(interval_seconds=3600):
    while True:
        try:
            check_and_send_reminders()
        except Exception as e:
            print(f"Scheduler Error: {e}")
        time.sleep(interval_seconds)

def logo_sync_loop(check_interval_seconds=60):
    """Gunde LOGO_SYNC_SAATLERI'nde bir kez Logo'dan veri ceker.

    Dakikada bir saat kontrolu yapilir; her saat icin gun basina tek
    calisma garanti edilir (calisan_saatler ile), yoksa 60 saniyelik
    kontrol araligi ayni saat icinde birden fazla tetikleme yapabilir.
    """
    calisan_saatler = set()  # (tarih, saat) ciftleri

    while True:
        try:
            now = datetime.now()
            anahtar = (now.date(), now.hour)
            if now.hour in LOGO_SYNC_SAATLERI and anahtar not in calisan_saatler:
                calisan_saatler.add(anahtar)
                if get_logo_settings().get('logo_auto_sync') != 'ON':
                    print(f"Logo senkronizasyonu ({now.hour}:00): otomatik senkron kapalı, atlandı.")
                else:
                    eklenen, sure_bekleyen, atlanan = sync_logo_invoices()
                    abone, riskli = sync_logo_subscriptions()
                    urun, urun_atlanan = sync_logo_products()
                    yenileme_adayi = yenileme_adaylari_bul()
                    print(f"Logo senkronizasyonu ({now.hour}:00): {eklenen} lisans, "
                          f"{abone} abonelik, {urun} ürün, {yenileme_adayi} yenileme adayı.")
        except Exception as e:
            print(f"Logo Sync Scheduler Error: {e}")
        time.sleep(check_interval_seconds)

def yedekle_veritabani():
    if not os.path.exists(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    zaman_damgasi = datetime.now().strftime('%Y%m%d_%H%M%S')
    hedef = os.path.join(BACKUP_DIR, f'license_reminders_{zaman_damgasi}.db')
    shutil.copy2(DB_PATH, hedef)

    yedekler = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith('license_reminders_') and f.endswith('.db')
    )
    while len(yedekler) > BACKUP_TUTULACAK_ADET:
        eski = yedekler.pop(0)
        os.remove(os.path.join(BACKUP_DIR, eski))

    return hedef

def backup_loop(check_interval_seconds=300):
    calisan_gunler = set()  # tekrar yedek almamak icin gun bazinda isaretleme
    while True:
        try:
            now = datetime.now()
            if now.hour == BACKUP_SAATI and now.date() not in calisan_gunler:
                calisan_gunler.add(now.date())
                hedef = yedekle_veritabani()
                if hedef:
                    print(f"Veritabani yedeklendi: {hedef}")
        except Exception as e:
            print(f"Backup Scheduler Error: {e}")
        time.sleep(check_interval_seconds)

def start_background_scheduler():
    thread = threading.Thread(target=scheduler_loop, args=(300,), daemon=True)
    thread.start()

    logo_thread = threading.Thread(target=logo_sync_loop, daemon=True)
    logo_thread.start()

    backup_thread = threading.Thread(target=backup_loop, daemon=True)
    backup_thread.start()

    print("Background reminder scheduler started.")

if __name__ == '__main__':
    count = check_and_send_reminders()
    print(f"Reminder check completed. Reminders sent: {count}")
