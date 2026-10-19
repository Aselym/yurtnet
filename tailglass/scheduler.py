import os
import shutil
import threading
import time
from datetime import datetime
from database import DB_PATH, get_db_connection, get_settings, setting_int_list, sure_dolmuslari_isaretle
from logo_sync import tam_senkron
from mailer import send_reminder_email
from notifier import send_windows_toast

# license_reminders.db Logo'dan cekilemeyen veriyi de tutuyor (teklifler,
# hatirlatma gecmisi, yenileme kararlari) — hicbir yere yedeklenmiyordu.
# Gece, kullanim olmayan bir saatte gunluk yedek alinir.
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')
BACKUP_SAATI = 4
BACKUP_TUTULACAK_ADET = 14

def _asama_durumu(idx, adet):
    if idx == adet - 1:
        return 'FINAL_REMINDER_SENT', 'FINAL_REMINDER'
    if idx == 0:
        return 'FIRST_REMINDER_SENT', 'FIRST_REMINDER'
    return 'SECOND_REMINDER_SENT', 'SECOND_REMINDER'


def check_and_send_reminders():
    """Hatirlatma asamalari kullanicinin ayarindan gelir (varsayilan 10,5,1 gun).

    Her lisansin kac asamasinin gonderildigi `reminders_sent_count`'ta tutulur.
    Uygulama birkac gun kapali kaldiysa ve birden fazla asama birden geldiyse
    yalnizca en acil olani gonderilir (ekip ayni lisans icin uc mail almasin).
    """
    sure_dolmuslari_isaretle()
    ayarlar = get_settings()
    asamalar = setting_int_list(ayarlar, 'reminder_days', '10,5,1')   # buyukten kucuge

    conn = get_db_connection()
    cursor = conn.cursor()
    # NEEDS_DURATION: bitis tarihi tahmin olacagi icin hatirlatma uretilmez.
    # RENEWED: bitisi gecmiste; dahil edilirse asagidaki days_left <= 0
    # kontrolu onlari sessizce EXPIRED'a cevirir (bkz. sure_dolmuslari_isaretle).
    cursor.execute("""
        SELECT * FROM sales
        WHERE status NOT IN ('EXPIRED', 'NEEDS_DURATION', 'RENEWED')
          AND COALESCE(duration_months, 0) > 0
    """)
    sales = [dict(row) for row in cursor.fetchall()]

    today = datetime.now().date()
    sent_count = 0
    for sale in sales:
        exp_date = datetime.strptime(sale['expiration_date'], '%Y-%m-%d').date()
        days_left = (exp_date - today).days
        if days_left <= 0:
            cursor.execute("UPDATE sales SET status = 'EXPIRED' WHERE id = ?", (sale['id'],))
            conn.commit()
            continue
        gonderilen = sale.get('reminders_sent_count') or 0
        hedef = max((i for i, gun in enumerate(asamalar) if days_left <= gun), default=None)
        if hedef is None or hedef < gonderilen:
            continue
        durum, asama = _asama_durumu(hedef, len(asamalar))
        success, msg = send_reminder_email(sale, asama)
        if success:
            cursor.execute('UPDATE sales SET status = ?, reminders_sent_count = ? WHERE id = ?',
                           (durum, hedef + 1, sale['id']))
            conn.commit()
            sent_count += 1
            send_windows_toast("Lisans Süresi Yaklaşıyor",
                               f"{sale['client_name']} - {sale['product_name']} ({days_left} gün kaldı)")
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
    """Ayarlardaki saatlerde (varsayilan 11,15,17) gunde bir kez senkron.

    Dakikada bir saat kontrolu yapilir; her (gun, saat) icin tek calisma.
    """
    calisan_saatler = set()
    while True:
        try:
            now = datetime.now()
            ayarlar = get_settings()
            saatler = set(setting_int_list(ayarlar, 'sync_hours', '11,15,17'))
            anahtar = (now.date(), now.hour)
            if now.hour in saatler and anahtar not in calisan_saatler:
                calisan_saatler.add(anahtar)
                if ayarlar.get('logo_auto_sync') != 'ON':
                    print(f"Logo senkronizasyonu ({now.hour}:00): otomatik senkron kapalı, atlandı.")
                else:
                    sonuc = tam_senkron()
                    print(f"Logo senkronizasyonu ({now.hour}:00): {sonuc.get('message')}")
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
