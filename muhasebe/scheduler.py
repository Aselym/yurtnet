import threading
import time
from datetime import datetime
from database import get_db_connection
from mailer import send_reminder_email, send_invoice_reminder
from notifier import send_windows_toast

def check_and_send_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM sales WHERE status != "EXPIRED"')
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

def check_and_send_invoice_reminders():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM invoices WHERE status = "UNPAID"')
    invoices = [dict(row) for row in cursor.fetchall()]

    today = datetime.now().date()
    sent_count = 0

    for inv in invoices:
        due_date = datetime.strptime(inv['due_date'], '%Y-%m-%d').date()
        days_left = (due_date - today).days
        stage = inv['reminder_stage']
        inv_id = inv['id']

        if days_left < 0 and stage != 'OVERDUE_SENT':
            success, msg = send_invoice_reminder(inv, 'OVERDUE')
            if success:
                cursor.execute('UPDATE invoices SET reminder_stage = "OVERDUE_SENT" WHERE id = ?', (inv_id,))
                conn.commit()
                sent_count += 1
                send_windows_toast("Vadesi Geçmiş Fatura", f"{inv['client_name']} - {inv['amount']} {inv['currency']} (Vade: {inv['due_date']})")

        elif 0 <= days_left <= 1 and stage not in ('DAY_SENT', 'OVERDUE_SENT'):
            success, msg = send_invoice_reminder(inv, 'DAY')
            if success:
                cursor.execute('UPDATE invoices SET reminder_stage = "DAY_SENT" WHERE id = ?', (inv_id,))
                conn.commit()
                sent_count += 1
                send_windows_toast("Fatura Vadesi Yarın Doluyor", f"{inv['client_name']} - {inv['amount']} {inv['currency']}")

        elif 1 < days_left <= 7 and stage == 'NONE':
            success, msg = send_invoice_reminder(inv, 'WEEK')
            if success:
                cursor.execute('UPDATE invoices SET reminder_stage = "WEEK_SENT" WHERE id = ?', (inv_id,))
                conn.commit()
                sent_count += 1
                send_windows_toast("Fatura Vadesi Yaklaşıyor", f"{inv['client_name']} - {days_left} gün kaldı")

    conn.close()
    return sent_count

def scheduler_loop(interval_seconds=3600):
    while True:
        try:
            check_and_send_reminders()
            check_and_send_invoice_reminders()
        except Exception as e:
            print(f"Scheduler Error: {e}")
        time.sleep(interval_seconds)

def start_background_scheduler():
    thread = threading.Thread(target=scheduler_loop, args=(300,), daemon=True)
    thread.start()
    print("Background reminder scheduler started.")

if __name__ == '__main__':
    count = check_and_send_reminders() + check_and_send_invoice_reminders()
    print(f"Reminder check completed. Reminders sent: {count}")
