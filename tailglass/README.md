# Tailglass Analytics — Logo ERP için satış, stok ve lisans analizi

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
