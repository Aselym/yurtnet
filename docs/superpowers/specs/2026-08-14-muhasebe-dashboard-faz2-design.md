# Muhasebe Frontend Faz 2 — Alt-proje 1: Dashboard

## Bağlam ve Amaç

Faz 1 (giriş, rol seçimi, yükleme animasyonu, iskelet paneller) main'e
merge edildi ve çalışıyor. Faz 2, `"satis"` rolü seçildiğinde açılan
`PlaceholderPanel` stub'ının yerini gerçek bir operasyon ekranıyla
değiştiriyor.

Faz 2'nin tamamı ("Ana Dashboard", "Akıllı Mail Otomasyonu", "Teklifler
Kanban Panosu") üç bağımsız alt-sistem içeriyor; kullanıcıyla birlikte bunu
üç ayrı spec/plan/uygulama döngüsüne bölmeye karar verildi. Bu spec yalnızca
**ilk alt-projeyi (Dashboard)** kapsar. Sıralama: Dashboard → Mail Modalı →
Teklifler Kanban.

## Mimari

`src/App.tsx`'teki state machine değişmiyor (`checking → login → role-select
→ transition → panel`), yalnızca `panel` adımında `role === 'satis'` için
gösterilen bileşen `PlaceholderPanel`'den `DashboardPage`'e değişiyor.
`role === 'yonetici'` hâlâ `PlaceholderPanel` kullanıyor (Faz 3'ün işi).

Sayfa içi gezinme (Özet / Lisanslar / Abonelikler / Ürünler / Teklifler)
React state ile yönetiliyor — istemci tarafı router yok, çünkü backend
(`muhasebe/app.py`'nin `do_GET`'i) hâlâ yalnızca `/`, `/login`, `/dashboard`
yollarını `index.html` ile eşliyor.

Layout: sol sabit kenar çubuğu (sidebar) + sağda içerik alanı — kurumsal
SaaS ürünlerinde standart desen, Faz 1'in premium hissini sürdürür.

## Bileşen Yapısı

```
src/
  lib/
    api.ts                        # getStats/getSales/getSubscriptions/getProducts
  pages/
    DashboardPage.tsx             # sidebar + aktif sekmeye göre içerik
  components/dashboard/
    Sidebar.tsx                   # nav: Özet, Lisanslar, Abonelikler, Ürünler, Teklifler, Çıkış
    StatCard.tsx                  # tek KPI kartı
    OverviewTab.tsx               # 5 KPI kartından oluşan grid
    DataTable.tsx                 # arama + tablo + boş/yükleniyor/hata durumları (jenerik kabuk)
    LicensesTab.tsx               # /api/sales -> DataTable, status pill
    SubscriptionsTab.tsx          # /api/subscriptions -> DataTable, status pill
    ProductsTab.tsx               # /api/products -> DataTable
    ComingSoonTab.tsx             # Teklifler sekmesi için geçici "yakında" içeriği
```

`lib/api.ts`, `lib/auth.ts` ile aynı desende: her fonksiyon backend'in
mevcut, değişmeyen endpoint'lerini sarmalar —

- `GET /api/stats` → `{total_sales, active_licenses, expiring_soon,
  reminders_sent, expired_licenses}`
- `GET /api/sales` → satış/lisans listesi (`days_left` backend'de hesaplanmış
  gelir)
- `GET /api/subscriptions` → abonelik listesi
- `GET /api/products` → ürün listesi

Backend'de **hiçbir değişiklik yok** — bu alt-proje salt okunur, mevcut
endpoint'leri tüketiyor.

## Kapsam Dışı (bu alt-projede yapılmayacak)

- "Müşteriye Mail Gönder" aksiyonu (alt-proje 2).
- Teklifler'in gerçek içeriği / Kanban panosu (alt-proje 3) — bu alt-projede
  yalnızca sidebar'da görünüp tıklanınca "yakında" yazan bir ekran açar.
- Süresi bilinmeyen (`NEEDS_DURATION`) lisanslara süre girme aksiyonu.
- Yenileme adayı onay/red aksiyonu (`/api/renewals`, `/api/sales/{id}/renewal`).

Bu üçü mevcut eski arayüzde vardı ama kullanıcının orijinal Faz 2 isteğinde
yoktu; sessizce atlanmıyor, ileride ayrı bir iyileştirme olarak eklenebilir.

## Veri Akışı ve Hata Yönetimi

Her sekme bileşeni kendi `useEffect` + `useState` ile bağımsız fetch yapar
(ek bir data-fetching kütüphanesi yok — YAGNI, veri hacmi küçük ve tek
kullanıcılı iç araç). Sekmeye ilk girişte veri çekilir; sekmeden çıkıp
geri dönüldüğünde önbellek yok, tekrar çekilir (basitlik tercih edildi).

Yükleniyor durumunda `DataTable` iskelet satırları gösterir. Fetch
başarısız olursa (network hatası veya `res.ok === false`), tablo yerine
"Veriler yüklenemedi, tekrar dene" mesajı + buton gösterilir; bir sekmenin
hatası diğer sekmeleri veya genel layout'u etkilemez (`lib/auth.ts`'teki
fail-safe desenle tutarlı).

## Test

Faz 1 ile tutarlı: bu fazda otomatik test paketi kurulmuyor. Doğrulama,
üretim build'i + Browser preview ile manuel QA (KPI kartlarının doğru
sayıları gösterdiği, her sekmenin gerçek veriyle dolduğu, arama/filtrenin
çalıştığı, hata durumunun simüle edilip "tekrar dene"nin işe yaradığı,
açık/koyu tema ve mobil genişlik kontrolleri).
