"""Analiz, stok, donem raporu, Excel, senkron ve ayar uclari.

app.py'deki el yapimi router'a eklenir: handle() True donerse istek
cevaplanmistir. Kimlik dogrulamasi app.py'de, buraya gelmeden yapilir.
"""

import json
import threading
import urllib.parse
from datetime import datetime

import analytics
import excel_export
import warehouse
from database import get_db_connection, get_settings
from logo_sync import tam_senkron, test_logo_connection

# ------------------------------------------------------------------ ayarlar
GIZLI = {'admin_pass_salt', 'admin_pass_hash'}
SIFRELER = {'smtp_password', 'logo_sql_pass'}
YAZILABILIR = {
    'smtp_host', 'smtp_port', 'smtp_user', 'smtp_password', 'sender_email', 'sender_name', 'internal_recipients',
    'logo_sql_server', 'logo_sql_port', 'logo_sql_db', 'logo_sql_user', 'logo_sql_pass', 'logo_firm_no',
    'logo_period_no', 'logo_auto_sync', 'logo_source', 'demo_db_path', 'data_start_date', 'license_min_expiry',
    'reminder_days', 'expiring_soon_days', 'sub_min_invoices', 'sub_max_interval_days', 'sub_risk_factor',
    'app_public_url', 'company_name', 'app_name', 'brand_color', 'base_currency', 'sync_hours', 'pinned_brands',
}


def ayarlari_oku():
    a = {k: v for k, v in get_settings().items() if k not in GIZLI}
    for k in SIFRELER:
        a[f'{k}_set'] = bool(a.get(k))
        a[k] = ''
    return a


def ayarlari_yaz(veri):
    conn = get_db_connection()
    try:
        for k, v in veri.items():
            if k not in YAZILABILIR:
                continue
            if k in SIFRELER and (v is None or v == ''):
                continue                      # bos gelen sifre mevcut sifreyi silmez
            conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (k, str(v)))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ senkron isi
_SYNC = {'running': False, 'started_at': None, 'step': None, 'result': None}
_SYNC_KILIT = threading.Lock()


def _senkron_calistir():
    def adim(m):
        _SYNC['step'] = m
    try:
        _SYNC['result'] = tam_senkron(adim)
    except Exception as e:                       # ham hata metni istemciye gitmez
        print(f"[Senkron hatasi] {e}")
        _SYNC['result'] = {'success': False, 'message': 'Senkron başarısız oldu. Bağlantı ayarlarını kontrol edin '
                                                        '(ayrıntı sunucu konsolunda).'}
    finally:
        _SYNC['running'] = False
        _SYNC['step'] = None


def senkron_baslat():
    with _SYNC_KILIT:
        if _SYNC['running']:
            return False
        _SYNC.update(running=True, started_at=datetime.now().isoformat(timespec='seconds'), result=None,
                     step='Başlatılıyor')
    threading.Thread(target=_senkron_calistir, daemon=True).start()
    return True


# ------------------------------------------------------------------ yardimci
def _satirlar(sql, params=()):
    conn = get_db_connection()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _yaz(sql, params=()):
    conn = get_db_connection()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _dosya_adi(on):
    return f"{on}-{datetime.now().strftime('%Y%m%d-%H%M')}.xlsx"


def siniflandirma_ozeti():
    return {
        'brand_sources': _satirlar("SELECT brand_src AS src, COUNT(*) AS n FROM wh_items GROUP BY 1"),
        'category_sources': _satirlar("SELECT category_src AS src, COUNT(*) AS n FROM wh_items GROUP BY 1"),
        # Kullanicinin elle bakmasi gerekenler: marka tahmin/bulunamadi, kategori bulunamadi
        'review': _satirlar("""
            SELECT i.item_ref, i.name, i.code, i.brand, i.brand_src, i.category, i.category_src, i.kind,
                   COALESCE(SUM(CASE WHEN l.direction='SATIS' AND l.cancelled=0 THEN l.net_tl END),0) AS sales_tl
            FROM wh_items i LEFT JOIN wh_lines l ON l.item_ref = i.item_ref
            WHERE i.brand_src IN ('tahmin','yok') OR i.category_src = 'yok'
            GROUP BY i.item_ref ORDER BY sales_tl DESC LIMIT 300"""),
    }


# ------------------------------------------------------------------ router
def handle(h, method, path, query, body):
    """h: BaseHTTPRequestHandler (app.py). Doner: istek cevaplandiysa True."""
    try:
        return _handle(h, method, path, query, body or {})
    except analytics.GecersizIstek as e:
        h._send_json({'success': False, 'message': str(e)}, 400)
        return True


def _handle(h, method, path, query, body):
    q = {k: v[0] for k, v in urllib.parse.parse_qs(query or '').items()}

    if method == 'GET':
        if path == '/api/meta':
            a = ayarlari_oku()
            h._send_json({**analytics.meta(), 'data': analytics.veri_araligi(), 'settings': {
                k: a.get(k) for k in ('app_name', 'company_name', 'brand_color', 'base_currency',
                                      'expiring_soon_days', 'reminder_days', 'logo_source', 'pinned_brands',
                                      'data_start_date', 'app_public_url')}})
            return True
        if path == '/api/settings':
            h._send_json(ayarlari_oku())
            return True
        if path == '/api/sync/durum':
            h._send_json({**_SYNC, 'data': analytics.veri_araligi()})
            return True
        if path == '/api/sync/gecmis':
            h._send_json(_satirlar("SELECT * FROM sync_log ORDER BY id DESC LIMIT 30"))
            return True
        if path == '/api/ara':
            h._send_json(analytics.deger_ara(q.get('boyut', 'client'), q.get('q', ''), int(q.get('limit', 30))))
            return True
        if path == '/api/kurallar':
            h._send_json(_satirlar("SELECT * FROM class_rules ORDER BY id"))
            return True
        if path == '/api/siniflandirma':
            h._send_json(siniflandirma_ozeti())
            return True
        if path == '/api/firma-gruplari':
            h._send_json(_satirlar("SELECT * FROM client_groups ORDER BY group_name, client_name"))
            return True
        if path == '/api/gorunumler':
            sayfa = q.get('page')
            sql = "SELECT * FROM saved_views" + (" WHERE page = ?" if sayfa else "") + " ORDER BY id DESC"
            rows = _satirlar(sql, (sayfa,) if sayfa else ())
            for r in rows:
                r['config'] = json.loads(r['config'])
            h._send_json(rows)
            return True
        return False

    if method == 'POST':
        if path == '/api/analiz/sorgu':
            h._send_json(analytics.sorgu(body))
            return True
        if path == '/api/analiz/satirlar':
            h._send_json(analytics.satirlar(body))
            return True
        if path == '/api/analiz/secenekler':
            h._send_json(analytics.secenekler(body))
            return True
        if path == '/api/genel-bakis':
            h._send_json(analytics.genel_bakis(body))
            return True
        if path == '/api/stok':
            h._send_json(analytics.stok(body))
            return True
        if path == '/api/donem-raporu':
            h._send_json(analytics.donem_raporu(body))
            return True
        if path.startswith('/api/export/'):
            tur = path.rsplit('/', 1)[-1]
            uretici = {'sorgu': excel_export.sorgu_excel, 'satirlar': excel_export.satirlar_excel,
                       'stok': excel_export.stok_excel, 'donem': excel_export.donem_excel}.get(tur)
            if not uretici:
                return False
            istek = body.get('request', body)
            veri = uretici(istek) if tur in ('stok', 'donem') else uretici(istek, body.get('title') or 'Analiz')
            h._send_bytes(veri, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                          _dosya_adi(body.get('filename') or tur))
            return True
        if path == '/api/sync/baslat':
            basladi = senkron_baslat()
            h._send_json({'success': basladi, 'message': 'Senkron başladı.' if basladi else 'Zaten çalışıyor.'})
            return True
        if path == '/api/logo/test-connection':
            ok, mesaj = test_logo_connection()
            h._send_json({'success': ok, 'message': mesaj})
            return True
        if path == '/api/settings':
            ayarlari_yaz(body)
            h._send_json({'success': True, 'message': 'Ayarlar kaydedildi.'})
            return True
        if path == '/api/kurallar':
            alan, desen, deger = body.get('field'), (body.get('pattern') or '').strip(), (body.get('value') or '').strip()
            if alan not in ('brand', 'category', 'revenue_type') or not desen or not deger:
                h._send_json({'success': False, 'message': 'Alan, aranacak metin ve değer gerekli.'}, 400)
                return True
            yeni = _yaz("INSERT INTO class_rules (field, pattern, value) VALUES (?,?,?)", (alan, desen, deger))
            n = warehouse.yeniden_siniflandir()
            h._send_json({'success': True, 'id': yeni, 'message': f'Kural eklendi, {n:,} ürün yeniden sınıflandırıldı.'})
            return True
        if path == '/api/siniflandirma/yenile':
            n = warehouse.yeniden_siniflandir()
            h._send_json({'success': True, 'message': f'{n:,} ürün yeniden sınıflandırıldı.'})
            return True
        if path == '/api/firma-gruplari':
            firmalar = [f.strip() for f in (body.get('client_names') or []) if f and f.strip()]
            grup = (body.get('group_name') or '').strip()
            if not firmalar or not grup:
                h._send_json({'success': False, 'message': 'Grup adı ve en az bir firma gerekli.'}, 400)
                return True
            conn = get_db_connection()
            conn.executemany("INSERT OR REPLACE INTO client_groups (client_name, group_name) VALUES (?,?)",
                             [(f, grup) for f in firmalar])
            conn.commit()
            conn.close()
            import lisans_takip
            lisans_takip.abonelikleri_turet()
            h._send_json({'success': True, 'message': f'{len(firmalar)} firma "{grup}" grubuna eklendi; '
                                                      'abonelik sağlığı yeniden hesaplandı.'})
            return True
        if path == '/api/gorunumler':
            ad, sayfa = (body.get('name') or '').strip(), body.get('page')
            if not ad or not sayfa:
                h._send_json({'success': False, 'message': 'Görünüm adı gerekli.'}, 400)
                return True
            yeni = _yaz("INSERT INTO saved_views (name, page, config) VALUES (?,?,?)",
                        (ad, sayfa, json.dumps(body.get('config') or {}, ensure_ascii=False)))
            h._send_json({'success': True, 'id': yeni, 'message': 'Görünüm kaydedildi.'})
            return True
        if path == '/api/demo/olustur':
            import os, subprocess, sys
            betik = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dev', 'demo_logo.py')
            r = subprocess.run([sys.executable, betik], capture_output=True, text=True, timeout=600)
            h._send_json({'success': r.returncode == 0,
                          'message': 'Demo veritabanı oluşturuldu.' if r.returncode == 0 else 'Oluşturulamadı.'})
            return True
        return False

    if method == 'DELETE':
        for onek, tablo, anahtar in (('/api/kurallar/', 'class_rules', 'id'), ('/api/gorunumler/', 'saved_views', 'id'),
                                     ('/api/firma-gruplari/', 'client_groups', 'client_name')):
            if path.startswith(onek):
                deger = urllib.parse.unquote(path[len(onek):])
                _yaz(f"DELETE FROM {tablo} WHERE {anahtar} = ?", (deger,))
                if tablo == 'class_rules':
                    warehouse.yeniden_siniflandir()
                if tablo == 'client_groups':
                    import lisans_takip
                    lisans_takip.abonelikleri_turet()
                h._send_json({'success': True, 'message': 'Silindi.'})
                return True
        return False
    return False
