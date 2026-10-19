"""Tailglass Analytics'in temiz dagitimi: yeni bir sirkete kurulacak surum.

Kaynak tek: muhasebe/ (Piramit Bilgisayar kurulumu). Bu betik ondan Piramit'e
ozgu her seyi (sirket adi ve logosu, canli veritabani, Piramit kurulum
betikleri) ayiklayip ../tailglass klasorune kendi basina calisan bir kurulum
uretir. Urun adi ve Tailglass logosu kodun icinde sabittir; sirket adi ve
logosu kurulumdan sonra Ayarlar > Sirket'ten girilir. muhasebe'ye eklenen her
ozellik betik yeniden calistirilinca dagitima da gecer.

    python dev/dagitim_uret.py            # uret + arayuzu derle
    python dev/dagitim_uret.py --no-build # sadece dosyalar
"""

import argparse
import os
import shutil
import subprocess
import sys

KAYNAK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEDEF = os.path.join(os.path.dirname(KAYNAK), 'tailglass')

HARIC_KLASOR = {'__pycache__', 'node_modules', 'backups', '.git', 'static'}
HARIC_DOSYA = {'license_reminders.db', 'build-output.txt', 'DEPLOY.md', 'DEPLOY_LINUX.md', 'server.ps1',
               'start_hidden.vbs', 'dagitim_uret.py', 'logo.png', 'logo2.png', 'logo-dark.png'}
METIN_UZANTI = {'.py', '.ts', '.tsx', '.css', '.html', '.json', '.md', '.sh', '.ps1', '.txt', '.yaml', '.service'}

DEGISIMLER = [
    # varsayilan ayarlar: sirket bos (Ayarlar'dan girilir), demo veriyle baslar
    ("('company_name', 'Piramit Bilgisayar')", "('company_name', '')"),
    ("('logo_source', 'mssql')", "('logo_source', 'demo')"),
    ('Piramit Muhasebe', 'Tailglass Analytics'), ('PiramitMuhasebe', 'TailglassAnalytics'),
    ('piramit-muhasebe', 'tailglass'), ('Piramit Lisans Takip', 'Tailglass Analytics'),
    ('Piramit Bilgisayar', 'Örnek Şirket'), ('Piramit', 'Örnek Şirket'), ('piramit', 'ornek'),
]

README = '''# Tailglass Analytics — Logo ERP için satış, stok ve lisans analizi

Tailglass Analytics, Logo ERP (Tiger / Go / Netsis değil, Logo'nun MS SQL tabloları) kullanan
bir işletmenin satış, alış, stok ve süreli lisans/abonelik verisini tek yerden
analiz etmesini sağlar. Logo'ya **asla yazmaz**; salt-okunur bağlanır.

## Ne yapar

- **Genel bakış:** dönem satışı, ürün / tekrarlayan gelir ayrımı, brüt kâr (FIFO),
  önceki dönem ya da geçen yılla karşılaştırma
- **Satışlar / Alışlar:** fatura satırları; müşteriye, ürüne, markaya… göre gruplu
  (aç/kapa) ya da satır satır; satılan ürünün alış tarihi ve depoda bekleme süresi
- **Ürünler ve stok:** herhangi bir tarihteki stok ve değeri, ölü stok, kaç gün yeter
- **Analiz:** pivot tablo — 4 kırılım, kolon boyutu, 15+ ölçü, ısı haritası, grafik,
  kayıtlı görünümler
- **Dönem raporu:** dönem başı stok + alış − satılan malın maliyeti = dönem sonu stok
- **Lisanslar / Abonelikler:** süresi dolacaklar, otomatik e-posta hatırlatması,
  yenileme eşleştirme, gecikmiş abonelik faturaları (firma grupları ile)
- Her tablo filtreleriyle **Excel'e** aktarılır

Her eşik ve kural (hatırlatma günleri, risk eşikleri, veri başlangıç tarihi,
marka/kategori kuralları) Ayarlar'dan değiştirilir; kod içinde sabit sayı yoktur.

## İlk çalıştırma (demo)

```
pip install -r requirements.txt
python dev/demo_sunucu.py
```

Tarayıcıda http://localhost:5050 — kullanıcı `admin`, şifre `Aa123456` (ilk girişte
Ayarlar > Hesap'tan değiştirin). Demo veri, Logo tablolarının birebir kopyası olan
örnek bir veritabanıdır (~95 bin satır, 10 yıl).

## Kendi Logo'nuza bağlama

```
python app.py
```

Ayarlar > Veri kaynağı: "Logo (MS SQL Server)" seçin; sunucu, veritabanı, salt-okunur
kullanıcı, firma ve dönem numarasını girin (birden fazla dönem: `01,02,03`).
Bağlantıyı test edip üst çubuktaki senkron düğmesine basın. Logo kullanıcısının
yalnızca `db_datareader` rolü olması yeterlidir.

Ayarlar > Şirket: şirket adı ve logosu (açık ve koyu tema için ayrı yüklenebilir).
Ürün adı ve Tailglass logosu sabittir, üst çubuğun sağında görünür.

## Testler

```
python -m unittest discover -s tests -v
```

## Yapı

| Dosya | Görev |
|---|---|
| `logo_source.py` | Logo okuma (MS SQL ya da demo SQLite — aynı SQL) |
| `warehouse.py` | Logo -> yerel ambar senkronu, FIFO maliyet |
| `siniflandirma.py` | Marka/kategori/tür/gelir tipi (kural > Logo > sözlük > tahmin) |
| `lisans_takip.py` | Lisans, abonelik, yenileme türetme |
| `analytics.py` | Analiz motoru (beyaz listeli boyut/ölçü) |
| `excel_export.py` | Excel çıktıları |
| `api_v2.py`, `app.py` | HTTP uçları (stdlib, framework yok) |
| `frontend/` | React + Vite arayüz (`npm run build` -> `static/`) |
| `dev/demo_logo.py` | Logo taklidi demo veritabanı üreticisi |
'''


def kopyala():
    if os.path.exists(HEDEF):
        # node_modules'u koru (npm install tekrar etmesin), gerisini temizle
        for ad in os.listdir(HEDEF):
            yol = os.path.join(HEDEF, ad)
            if ad in ('frontend',):
                for alt in os.listdir(yol):
                    if alt != 'node_modules':
                        p = os.path.join(yol, alt)
                        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                continue
            if ad.endswith('.db') or ad == 'backups':
                continue                         # kurulumun kendi verisi korunur
            shutil.rmtree(yol) if os.path.isdir(yol) else os.remove(yol)
    for kok, klasorler, dosyalar in os.walk(KAYNAK):
        klasorler[:] = [k for k in klasorler if k not in HARIC_KLASOR]
        rel = os.path.relpath(kok, KAYNAK)
        hedef_kok = HEDEF if rel == '.' else os.path.join(HEDEF, rel)
        os.makedirs(hedef_kok, exist_ok=True)
        for d in dosyalar:
            if d in HARIC_DOSYA or d.endswith(('.db', '.db-wal', '.db-shm', '.pyc', '.tsbuildinfo')):
                continue
            kaynak_yol, hedef_yol = os.path.join(kok, d), os.path.join(hedef_kok, d)
            if os.path.splitext(d)[1] in METIN_UZANTI:
                metin = open(kaynak_yol, encoding='utf-8').read()
                for a, b in DEGISIMLER:
                    metin = metin.replace(a, b)
                open(hedef_yol, 'w', encoding='utf-8', newline='').write(metin)
            else:
                shutil.copy2(kaynak_yol, hedef_yol)

    open(os.path.join(HEDEF, 'README.md'), 'w', encoding='utf-8').write(README)

    # Kalinti kontrolu: Piramit adi hicbir kaynak dosyada kalmamali
    kalan = []
    for kok, klasorler, dosyalar in os.walk(HEDEF):
        klasorler[:] = [k for k in klasorler if k != 'node_modules']
        for d in dosyalar:
            if os.path.splitext(d)[1] in METIN_UZANTI:
                if 'piramit' in open(os.path.join(kok, d), encoding='utf-8', errors='ignore').read().lower():
                    kalan.append(os.path.relpath(os.path.join(kok, d), HEDEF))
    return kalan


def derle():
    fe = os.path.join(HEDEF, 'frontend')
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    if not os.path.exists(os.path.join(fe, 'node_modules')):
        subprocess.run([npm, 'install', '--no-audit', '--no-fund'], cwd=fe, check=True)
    subprocess.run([npm, 'run', 'build'], cwd=fe, check=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--no-build', action='store_true')
    a = p.parse_args()
    kalan = kopyala()
    print(f'Tailglass dağıtımı üretildi: {HEDEF}')
    if kalan:
        print('UYARI — Piramit adı hâlâ geçiyor:', ', '.join(kalan))
        sys.exit(1)
    if not a.no_build:
        derle()
        print('Arayüz derlendi.')
