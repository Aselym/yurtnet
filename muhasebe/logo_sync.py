import sqlite3
import re
from datetime import datetime
from database import get_db_connection, calculate_dates

def get_logo_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT key, value FROM settings')
    rows = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def build_connection_string(settings):
    server = settings.get('logo_sql_server', '127.0.0.1')
    port = settings.get('logo_sql_port', '1433')
    database = settings.get('logo_sql_db', 'LOGO')
    user = settings.get('logo_sql_user', 'sa')
    password = settings.get('logo_sql_pass', '')

    driver_name = 'ODBC Driver 17 for SQL Server'
    try:
        import pyodbc
        available_drivers = pyodbc.drivers()
        for d in ['ODBC Driver 17 for SQL Server', 'ODBC Driver 18 for SQL Server', 'SQL Server']:
            if d in available_drivers:
                driver_name = d
                break
    except Exception:
        pass

    return f"DRIVER={{{driver_name}}};SERVER={server},{port};DATABASE={database};UID={user};PWD={password};Timeout=5;"

def test_logo_connection():
    settings = get_logo_settings()
    conn_str = build_connection_string(settings)

    try:
        import pyodbc
        conn = pyodbc.connect(conn_str)
        conn.close()
        return True, "Logo MS SQL Server bağlantısı başarılı."
    except ImportError:
        return False, "pyodbc kütüphanesi yüklü değil. (pip install pyodbc)"
    except Exception as e:
        return False, f"SQL Bağlantı Hatası: {str(e)}"

def extract_duration_months(product_name):
    text = product_name.upper()
    
    year_match = re.search(r'(\d+)\s*(YIL|YEAR)', text)
    if year_match:
        return int(year_match.group(1)) * 12

    month_match = re.search(r'(\d+)\s*(AY|MONTH)', text)
    if month_match:
        return int(month_match.group(1))

    return 36

def sync_logo_invoices():
    settings = get_logo_settings()
    firm_no = settings.get('logo_firm_no', '001').zfill(3)
    period_no = settings.get('logo_period_no', '01').zfill(2)

    conn_str = build_connection_string(settings)
    imported_count = 0

    try:
        import pyodbc
        sql_conn = pyodbc.connect(conn_str)
        cursor = sql_conn.cursor()

        query = f'''
            SELECT 
                INV.FICHENO AS FaturaNo,
                INV.DATE_ AS FaturaTarihi,
                CLC.DEFINITION_ AS MusteriUnvani,
                CLC.EMAILADDR AS MusteriEmail,
                ITM.NAME AS UrunAdi,
                ST.SPECODE AS LisansKey,
                CLC.SPECODE AS SatisTemsilcisi
            FROM LG_{firm_no}_{period_no}_INVOICE INV WITH (NOLOCK)
            INNER JOIN LG_{firm_no}_{period_no}_STLINE ST WITH (NOLOCK) ON ST.INVOICEREF = INV.LOGICALREF
            LEFT JOIN LG_{firm_no}_CLCARD CLC WITH (NOLOCK) ON CLC.LOGICALREF = INV.CLIENTREF
            LEFT JOIN LG_{firm_no}_ITEMS ITM WITH (NOLOCK) ON ITM.LOGICALREF = ST.STOCKREF
            WHERE INV.TRCODE IN (7, 8) 
              AND INV.CANCELLED = 0
              AND (ITM.NAME LIKE '%LISANS%' OR ITM.NAME LIKE '%LICENSE%' OR ITM.NAME LIKE '%WATCHGUARD%' OR ITM.NAME LIKE '%FORTIGATE%' OR ITM.NAME LIKE '%MICROSOFT%')
            ORDER BY INV.DATE_ DESC
        '''
        cursor.execute(query)
        rows = cursor.fetchall()
        sql_conn.close()

    except Exception as e:
        print(f"Logo MS SQL Sync Error (Live SQL fallback to simulation mode): {e}")
        rows = []

    sqlite_conn = get_db_connection()
    db_cursor = sqlite_conn.cursor()

    for row in rows:
        fatura_no = str(row[0]).strip()
        fatura_tarihi_raw = row[1]
        
        if isinstance(fatura_tarihi_raw, datetime):
            sale_date = fatura_tarihi_raw.strftime('%Y-%m-%d')
        else:
            sale_date = str(fatura_tarihi_raw)[:10]

        client_name = row[2] or 'Bilinmeyen Müşteri'
        client_email = row[3] or 'bilgi@musteri.com'
        product_name = row[4] or 'Logo ERP Lisanslı Ürün'
        license_key = row[5] or f"LOGO-{fatura_no}"
        sales_rep = row[6] or 'Logo Entegrasyon'

        db_cursor.execute('SELECT COUNT(*) FROM sales WHERE notes LIKE ? OR license_key = ?', (f'%Fatura No: {fatura_no}%', license_key))
        if db_cursor.fetchone()[0] > 0:
            continue

        duration_months = extract_duration_months(product_name)
        duration_type = '3_YEARS' if duration_months == 36 else '1_YEAR' if duration_months == 12 else 'CUSTOM'
        expiration_date = calculate_dates(sale_date, duration_months)
        notes = f"Logo ERP Entegrasyonu ile Otomatik Aktarıldı (Fatura No: {fatura_no})"

        db_cursor.execute('''
            INSERT INTO sales (product_name, client_name, client_email, sales_rep, license_key, sale_date, duration_type, duration_months, expiration_date, reminder_type, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'STAGED', 'PENDING', ?)
        ''', (product_name, client_name, client_email, sales_rep, license_key, sale_date, duration_type, duration_months, expiration_date, notes))
        
        imported_count += 1

    sqlite_conn.commit()
    sqlite_conn.close()

    return imported_count

if __name__ == '__main__':
    count = sync_logo_invoices()
    print(f"Logo ERP sync finished. Imported: {count}")
