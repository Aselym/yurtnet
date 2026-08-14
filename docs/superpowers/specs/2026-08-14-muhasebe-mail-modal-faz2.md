# Muhasebe Frontend Faz 2 — Alt-proje 2: Mail Otomasyonu Modalı

## Bağlam ve Amaç

Faz 2'nin ilk alt-projesi (Dashboard) main'e merge edildi. Bu spec ikinci
alt-projeyi kapsar: Lisanslar tablosundaki her kayıt için tek tıkla
hatırlatma gönderme akışı.

## Kritik netleştirme (kullanıcıyla doğrulandı)

Backend'deki `POST /api/sales/{id}/send-reminder` endpoint'i **müşteriye
değil**, `settings` tablosundaki `internal_recipients`'e (muhasebe/satış
ekibinin kendi adreslerine) mail gönderiyor — içerik de ekibe "bu müşteriye
yenileme teklifi hazırlamanız gerekiyor" diyen bir iç bildirim, müşteriye
hitap eden bir metin değil (bkz. `muhasebe/mailer.py`'deki `lisans_maili`).

Kullanıcı bunu bilinçli olarak onayladı: buton arayüzde "Müşteriye Mail
Gönder" gibi görünse de işlevi ekip-içi bildirim olarak kalacak — ama
tıklandığında **gerçek alıcı listesini açıkça gösteren bir onay adımı**
olacak, böylece kullanıcı nereye gittiğini görüp bilerek onaylayacak.
Backend'de **hiçbir değişiklik yapılmıyor**.

## Mimari

Lisanslar tablosuna (`LicensesTab.tsx`, Dashboard alt-projesinde
oluşturuldu) bir aksiyon sütunu eklenir. Tıklanınca `ReminderModal` açılır:

1. Modal açılırken mevcut `GET /api/settings` çağrılır, `internal_recipients`
   alanı virgülle ayrılmış adres listesi olarak parse edilir.
2. Modal, satırın zaten elde bulunan verisinden (müşteri, ürün, bitiş
   tarihi, kalan gün) bir özet ve gerçek alıcı listesini gösterir: "Bu
   bildirim şu adreslere gidecek: [...]. Emin misiniz?"
3. Onaylanınca mevcut `POST /api/sales/{id}/send-reminder` çağrılır.
   `stage` parametresi istemci tarafında hesaplanır: kalan gün ≤ 7 ise
   `FINAL_REMINDER`, değilse `FIRST_REMINDER` — `scheduler.py`'nin kendi
   eşikleriyle tutarlı.
4. Başarılıysa modal başarı mesajı gösterip kapanır. Başarısız olursa
   (örn. SMTP ayarı eksik) backend'in döndürdüğü gerçek hata mesajı modal
   içinde gösterilir, modal kapanmaz, kullanıcı tekrar deneyebilir.

## Bileşen Yapısı

```
src/
  lib/
    api.ts                          # eklenecek: getSettings(), sendReminder()
  components/dashboard/
    ReminderModal.tsx               # yeni
    LicensesTab.tsx                 # değişecek: aksiyon sütunu + modal state
```

`lib/api.ts`'e eklenecek:
- `getSettings(): Promise<Record<string, string> | null>` — `GET
  /api/settings`, mevcut fail-safe null-on-error deseniyle.
- `sendReminder(saleId: number, stage: 'FIRST_REMINDER' | 'FINAL_REMINDER'):
  Promise<{success: boolean; message: string}>` — `POST
  /api/sales/{id}/send-reminder`, backend zaten bu şekli döndürüyor.

## Kapsam Dışı

- Gerçekten müşteriye giden ayrı bir mail şablonu/endpoint'i (kullanıcı
  bilinçli olarak reddetti, bkz. yukarıdaki netleştirme).
- Abonelikler veya Ürünler sekmelerine benzer bir aksiyon eklemek — sadece
  Lisanslar tablosu kapsıyor.
- Gönderim geçmişi görüntüleme (`sent_emails` tablosu) — ayrı bir olası
  gelecek iyileştirme.

## Hata Yönetimi

`getSettings()` başarısız olursa modal alıcı listesini gösteremez;
"Alıcı listesi yüklenemedi" mesajıyla gönder butonu devre dışı bırakılır,
kullanıcı modalı kapatıp tekrar açabilir. `sendReminder()` başarısız
olursa backend'in mesajı olduğu gibi gösterilir (modal `lib/auth.ts`'teki
gibi bir throw yerine `{success, message}` döndüğü için özel bir catch
gerekmiyor, backend zaten kullanıcı dostu Türkçe hata mesajları üretiyor —
örn. "SMTP sunucu adresi girilmemiş").

## Test

Faz 1/Dashboard ile tutarlı: otomatik test yok. Manuel QA, hem SMTP ayarı
doğru hem de eksik olduğu iki senaryoyu da kapsayacak (başarı ve hata
mesajı yollarının ikisi de görülmeli).
