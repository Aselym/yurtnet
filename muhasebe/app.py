import os
import json
import uuid
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from database import init_db, get_db_connection, calculate_dates, hash_password, verify_password
from mailer import send_reminder_email, send_invoice_reminder
from scheduler import check_and_send_reminders, check_and_send_invoice_reminders, start_background_scheduler
from logo_sync import test_logo_connection, sync_logo_invoices
from notifier import send_windows_toast

PORT = 5000
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

ACTIVE_SESSIONS = set()

def _get_credentials():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings WHERE key IN ('admin_user','admin_pass_salt','admin_pass_hash')")
    rows = {r['key']: r['value'] for r in cursor.fetchall()}
    conn.close()
    return rows.get('admin_user', 'admin'), rows.get('admin_pass_salt', ''), rows.get('admin_pass_hash', '')

class LicenseReminderHTTPHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def _get_session_token(self):
        cookie_header = self.headers.get('Cookie')
        if not cookie_header:
            return None
        cookies = dict(item.strip().split('=', 1) for item in cookie_header.split(';') if '=' in item.strip())
        return cookies.get('session_token')

    def _is_authenticated(self):
        token = self._get_session_token()
        return token in ACTIVE_SESSIONS if token else False

    def _send_json(self, data, status_code=200, headers=None):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_file(self, file_path, mime_type):
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return
        self.send_response(200)
        self.send_header('Content-Type', f'{mime_type}')
        self.end_headers()
        with open(file_path, 'rb') as f:
            self.wfile.write(f.read())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path in ('/', '/index.html', '/login', '/dashboard'):
            self._send_file(os.path.join(STATIC_DIR, 'index.html'), 'text/html; charset=utf-8')
            return
        elif path == '/favicon.ico':
            logo_path = os.path.join(STATIC_DIR, 'images', 'logo2.png') if os.path.exists(os.path.join(STATIC_DIR, 'images', 'logo2.png')) else os.path.join(STATIC_DIR, 'images', 'logo.png')
            self._send_file(logo_path, 'image/png')
            return
        elif path.startswith('/static/'):
            rel_path = path[8:]
            file_path = os.path.join(STATIC_DIR, rel_path)
            mime = 'text/css; charset=utf-8' if path.endswith('.css') else \
                   'application/javascript; charset=utf-8' if path.endswith('.js') else \
                   'image/png' if path.endswith('.png') else \
                   'image/svg+xml' if path.endswith('.svg') else \
                   'image/jpeg' if path.endswith(('.jpg', '.jpeg')) else 'text/html'
            self._send_file(file_path, mime)
            return

        if path in ('/api/check-auth', '/check-auth'):
            if self._is_authenticated():
                admin_user, _, _ = _get_credentials()
                self._send_json({'authenticated': True, 'user': admin_user})
            else:
                self._send_json({'authenticated': False}, 401)
            return

        if path in ('/api/logout', '/logout'):
            token = self._get_session_token()
            if token in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS.remove(token)
            cookie_header = "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax"
            self._send_json({'success': True, 'redirect': '/login', 'message': 'Çıkış yapıldı.'}, 200, {'Set-Cookie': cookie_header})
            return

        if not self._is_authenticated():
            self._send_json({'error': 'Yetkisiz erişim. Lütfen giriş yapın.'}, 401)
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        if path == '/api/stats':
            cursor.execute('SELECT COUNT(*) FROM sales')
            total_sales = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM sales WHERE status != "EXPIRED"')
            active_licenses = cursor.fetchone()[0]

            cursor.execute('SELECT * FROM sales WHERE status != "EXPIRED"')
            rows = [dict(r) for r in cursor.fetchall()]
            expiring_soon = 0
            for r in rows:
                exp = datetime.strptime(r['expiration_date'], '%Y-%m-%d').date()
                days = (exp - datetime.now().date()).days
                if 0 < days <= 30:
                    expiring_soon += 1

            cursor.execute('SELECT COUNT(*) FROM sent_emails')
            total_reminders_sent = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM sales WHERE status = "EXPIRED"')
            expired_licenses = cursor.fetchone()[0]

            conn.close()
            self._send_json({
                'total_sales': total_sales,
                'active_licenses': active_licenses,
                'expiring_soon': expiring_soon,
                'reminders_sent': total_reminders_sent,
                'expired_licenses': expired_licenses
            })
            return

        elif path == '/api/sales':
            cursor.execute('SELECT * FROM sales ORDER BY id DESC')
            rows = [dict(r) for r in cursor.fetchall()]
            today = datetime.now().date()
            for r in rows:
                exp = datetime.strptime(r['expiration_date'], '%Y-%m-%d').date()
                r['days_left'] = (exp - today).days
            conn.close()
            self._send_json(rows)
            return

        elif path == '/api/sent-emails':
            cursor.execute('''
                SELECT sent_emails.*, sales.product_name 
                FROM sent_emails 
                LEFT JOIN sales ON sent_emails.sale_id = sales.id 
                ORDER BY sent_emails.id DESC
            ''')
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json(rows)
            return

        elif path == '/api/templates':
            cursor.execute('SELECT * FROM email_templates ORDER BY id ASC')
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            self._send_json(rows)
            return

        elif path == '/api/settings':
            cursor.execute('SELECT key, value FROM settings')
            rows = cursor.fetchall()
            conn.close()
            self._send_json({r['key']: r['value'] for r in rows})
            return

        elif path == '/api/invoices':
            cursor.execute('SELECT * FROM invoices ORDER BY due_date ASC')
            rows = [dict(r) for r in cursor.fetchall()]
            today = datetime.now().date()
            for r in rows:
                due = datetime.strptime(r['due_date'], '%Y-%m-%d').date()
                r['days_left'] = (due - today).days
            conn.close()
            self._send_json(rows)
            return

        elif path == '/api/notifications/pending':
            cursor.execute('SELECT client_name, product_name, expiration_date FROM sales WHERE status != "EXPIRED"')
            sales = [dict(r) for r in cursor.fetchall()]
            today = datetime.now().date()
            license_alerts = 0
            for s in sales:
                exp = datetime.strptime(s['expiration_date'], '%Y-%m-%d').date()
                if (exp - today).days <= 7:
                    license_alerts += 1

            cursor.execute('SELECT client_name, amount, currency, due_date FROM invoices WHERE status = "UNPAID"')
            invoices = [dict(r) for r in cursor.fetchall()]
            invoice_alerts = 0
            for i in invoices:
                due = datetime.strptime(i['due_date'], '%Y-%m-%d').date()
                if (due - today).days <= 7:
                    invoice_alerts += 1

            conn.close()
            self._send_json({
                'license_alerts': license_alerts,
                'invoice_alerts': invoice_alerts,
                'total': license_alerts + invoice_alerts
            })
            return

        conn.close()
        self.send_error(404, "Endpoint not found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        content_length = int(self.headers.get('Content-Length', 0))
        body_data = {}
        if content_length > 0:
            raw_body = self.rfile.read(content_length).decode('utf-8')
            try:
                body_data = json.loads(raw_body)
            except Exception:
                pass

        if path in ('/api/login', '/login'):
            username = body_data.get('username')
            password = body_data.get('password') or ''

            admin_user, admin_salt, admin_hash = _get_credentials()
            if username == admin_user and verify_password(password, admin_salt, admin_hash):
                token = str(uuid.uuid4())
                ACTIVE_SESSIONS.add(token)
                cookie_header = f"session_token={token}; Path=/; HttpOnly; SameSite=Lax"
                self._send_json({'success': True, 'redirect': '/dashboard', 'message': 'Giriş başarılı.'}, 200, {'Set-Cookie': cookie_header})
            else:
                self._send_json({'success': False, 'message': 'Kullanıcı adı veya şifre hatalı!'}, 401)
            return

        if path in ('/api/logout', '/logout'):
            token = self._get_session_token()
            if token in ACTIVE_SESSIONS:
                ACTIVE_SESSIONS.remove(token)
            cookie_header = "session_token=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax"
            self._send_json({'success': True, 'redirect': '/login', 'message': 'Çıkış yapıldı.'}, 200, {'Set-Cookie': cookie_header})
            return

        if not self._is_authenticated():
            self._send_json({'error': 'Yetkisiz erişim.'}, 401)
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        if path == '/api/sales':
            product_name = body_data.get('product_name')
            client_name = body_data.get('client_name')
            client_email = body_data.get('client_email')
            sales_rep = body_data.get('sales_rep', '')
            license_key = body_data.get('license_key', '')
            sale_date = body_data.get('sale_date') or datetime.now().strftime('%Y-%m-%d')
            duration_type = body_data.get('duration_type', '3_YEARS')
            duration_months = int(body_data.get('duration_months', 36))
            reminder_type = body_data.get('reminder_type', 'STAGED')
            notes = body_data.get('notes', '')

            expiration_date = calculate_dates(sale_date, duration_months)

            cursor.execute('''
                INSERT INTO sales (product_name, client_name, client_email, sales_rep, license_key, sale_date, duration_type, duration_months, expiration_date, reminder_type, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            ''', (product_name, client_name, client_email, sales_rep, license_key, sale_date, duration_type, duration_months, expiration_date, reminder_type, notes))

            sale_id = cursor.lastrowid
            conn.commit()
            conn.close()

            check_and_send_reminders()

            self._send_json({'success': True, 'id': sale_id, 'expiration_date': expiration_date, 'message': 'Satış kaydı başarıyla eklendi.'})
            return

        elif path.startswith('/api/sales/') and path.endswith('/send-reminder'):
            parts = path.split('/')
            sale_id = int(parts[3])
            cursor.execute('SELECT * FROM sales WHERE id = ?', (sale_id,))
            sale = cursor.fetchone()
            if not sale:
                conn.close()
                self._send_json({'success': False, 'message': 'Satış bulunamadı.'}, 404)
                return

            sale_data = dict(sale)
            stage = body_data.get('stage', 'FINAL_REMINDER')
            success, msg = send_reminder_email(sale_data, stage)
            conn.close()
            self._send_json({'success': success, 'message': msg})
            return

        elif path == '/api/sent-emails/clear':
            cursor.execute('DELETE FROM sent_emails')
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Sanal gelen kutusu temizlendi.'})
            return

        elif path == '/api/settings':
            for key, val in body_data.items():
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(val)))
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Sistem ayarları güncellendi.'})
            return

        elif path == '/api/logo/test-connection':
            conn.close()
            success, msg = test_logo_connection()
            self._send_json({'success': success, 'message': msg})
            return

        elif path == '/api/logo/sync':
            conn.close()
            count = sync_logo_invoices()
            self._send_json({'success': True, 'imported_count': count, 'message': f'Logo ERP senkronizasyonu tamamlandı. {count} yeni fatura aktarıldı.'})
            return

        elif path == '/api/run-scheduler':
            conn.close()
            sent_count = check_and_send_reminders() + check_and_send_invoice_reminders()
            self._send_json({'success': True, 'sent_count': sent_count, 'message': f'Hatırlatma kontrolü tamamlandı. Gönderilen: {sent_count}'})
            return

        elif path == '/api/invoices':
            invoice_no = body_data.get('invoice_no', '')
            client_name = body_data.get('client_name')
            client_email = body_data.get('client_email', '')
            amount = float(body_data.get('amount', 0))
            currency = body_data.get('currency', 'TRY')
            issue_date = body_data.get('issue_date') or datetime.now().strftime('%Y-%m-%d')
            due_date = body_data.get('due_date')
            notes = body_data.get('notes', '')

            cursor.execute('''
                INSERT INTO invoices (invoice_no, client_name, client_email, amount, currency, issue_date, due_date, status, reminder_stage, source, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'UNPAID', 'NONE', 'MANUAL', ?)
            ''', (invoice_no, client_name, client_email, amount, currency, issue_date, due_date, notes))
            invoice_id = cursor.lastrowid
            conn.commit()
            conn.close()

            self._send_json({'success': True, 'id': invoice_id, 'message': 'Fatura kaydı başarıyla eklendi.'})
            return

        elif path.startswith('/api/invoices/') and path.endswith('/send-reminder'):
            parts = path.split('/')
            invoice_id = int(parts[3])
            cursor.execute('SELECT * FROM invoices WHERE id = ?', (invoice_id,))
            invoice = cursor.fetchone()
            if not invoice:
                conn.close()
                self._send_json({'success': False, 'message': 'Fatura bulunamadı.'}, 404)
                return

            invoice_data = dict(invoice)
            stage = body_data.get('stage', 'WEEK')
            success, msg = send_invoice_reminder(invoice_data, stage)
            conn.close()
            self._send_json({'success': success, 'message': msg})
            return

        elif path.startswith('/api/invoices/') and path.endswith('/mark-paid'):
            parts = path.split('/')
            invoice_id = int(parts[3])
            cursor.execute('UPDATE invoices SET status = "PAID" WHERE id = ?', (invoice_id,))
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Fatura ödendi olarak işaretlendi.'})
            return

        elif path == '/api/account':
            current_password = body_data.get('current_password', '')
            new_username = (body_data.get('new_username') or '').strip()
            new_password = body_data.get('new_password', '')

            admin_user, admin_salt, admin_hash = _get_credentials()
            if not verify_password(current_password, admin_salt, admin_hash):
                conn.close()
                self._send_json({'success': False, 'message': 'Mevcut şifre hatalı.'}, 401)
                return

            final_username = new_username or admin_user
            cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('admin_user', final_username))

            if new_password:
                salt, pwd_hash = hash_password(new_password)
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('admin_pass_salt', salt))
                cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('admin_pass_hash', pwd_hash))

            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Hesap bilgileri güncellendi.'})
            return

        conn.close()
        self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        if not self._is_authenticated():
            self._send_json({'error': 'Yetkisiz erişim.'}, 401)
            return

        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        content_length = int(self.headers.get('Content-Length', 0))
        raw_body = self.rfile.read(content_length).decode('utf-8')
        body_data = json.loads(raw_body)

        conn = get_db_connection()
        cursor = conn.cursor()

        if path.startswith('/api/templates/'):
            template_key = path.split('/')[-1]
            subject = body_data.get('subject')
            body_html = body_data.get('body_html')

            cursor.execute('''
                UPDATE email_templates 
                SET subject = ?, body_html = ?, updated_at = CURRENT_TIMESTAMP
                WHERE template_key = ?
            ''', (subject, body_html, template_key))
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'E-posta şablonu güncellendi.'})
            return

        conn.close()
        self.send_error(404)

    def do_DELETE(self):
        if not self._is_authenticated():
            self._send_json({'error': 'Yetkisiz erişim.'}, 401)
            return

        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        conn = get_db_connection()
        cursor = conn.cursor()

        if path.startswith('/api/sales/'):
            sale_id = int(path.split('/')[-1])
            cursor.execute('DELETE FROM sales WHERE id = ?', (sale_id,))
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Satış kaydı silindi.'})
            return

        if path.startswith('/api/invoices/'):
            invoice_id = int(path.split('/')[-1])
            cursor.execute('DELETE FROM invoices WHERE id = ?', (invoice_id,))
            conn.commit()
            conn.close()
            self._send_json({'success': True, 'message': 'Fatura kaydı silindi.'})
            return

        conn.close()
        self.send_error(404)

def run_server():
    init_db()
    start_background_scheduler()
    server = HTTPServer(('0.0.0.0', PORT), LicenseReminderHTTPHandler)
    print(f"============================================================")
    print(f"  PIRAMIT LISANS TAKIP & E-POSTA HATIRLATMA UYGULAMASI     ")
    print(f"  Adres: http://localhost:{PORT}                              ")
    print(f"============================================================")
    send_windows_toast("Piramit Muhasebe", "Uygulama çalışıyor")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Sunucu durduruldu.")
        server.server_close()

if __name__ == '__main__':
    run_server()
