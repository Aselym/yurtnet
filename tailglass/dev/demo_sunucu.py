"""Demo sunucusu: gercek license_reminders.db'ye ASLA dokunmaz.

Ayri bir uygulama veritabani (dev/demo_app.db) ve sahte Logo
(dev/demo_logo.db) ile 5050 portunda calisir. Ilk acilista demo Logo yoksa
uretilir ve ambar senkronlanir.

    python dev/demo_sunucu.py
"""

import os
import sys

BURASI = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(BURASI)
os.environ['MUHASEBE_DB'] = os.path.join(BURASI, 'demo_app.db')
os.environ.setdefault('MUHASEBE_PORT', '5050')
sys.path.insert(0, KOK)
os.chdir(KOK)

from database import init_db, get_db_connection  # noqa: E402

init_db()
conn = get_db_connection()
conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('logo_source', 'demo')")
conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('app_public_url', 'http://localhost:5050')")
conn.commit()
bos = conn.execute('SELECT COUNT(*) FROM wh_lines').fetchone()[0] == 0
conn.close()

if not os.path.exists(os.path.join(BURASI, 'demo_logo.db')):
    import subprocess
    subprocess.run([sys.executable, os.path.join(BURASI, 'demo_logo.py')], check=True)
if bos:
    from logo_sync import tam_senkron
    print(tam_senkron(print).get('message'))

import app  # noqa: E402

app.run_server()
