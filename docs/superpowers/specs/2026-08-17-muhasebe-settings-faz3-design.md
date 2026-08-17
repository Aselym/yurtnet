# Muhasebe Frontend Faz 3 — Alt-proje 1: Ayarlar Modülü

## Bağlam ve Amaç

Faz 1 (Giriş/Rol Seçimi) ve Faz 2 (Satış/Muhasebe operasyon ekranı — Dashboard,
Mail Modalı, Kanban Teklif Panosu, ve devamında brainstorm edilen 6 alt-proje:
Yenileme Adayları, Müşteri 360°, Satış Temsilcisi Panosu, Marka Performansı,
Tek Tık Teklif, Yenileme Geliri Tahmini) main'de tamamlandı.

Faz 3 kapsamı ilk tasarımda ("Faz 1: Giriş ve Yönlendirme" spec'inin
"Kapsam Dışı" bölümünde) şöyle tanımlanmıştı: *Yönetici analiz dashboard'u,
sistem tespitleri widget'ı, ayarlar modülü.* Bu üç parça bağımsız
alt-projeler olarak ele alınacak; bu spec yalnızca **Ayarlar Modülü**'nü
kapsar. Sıradaki: Yönetici Analiz Dashboard'u, ardından Sistem Tespitleri
Widget'ı.

Backend tarafı bu modül için **zaten tamamen hazır** — `GET/POST
/api/settings`, `POST /api/account`, `POST /api/test-email`, `POST
/api/logo/test-connection`, `POST /api/logo/sync`. Eski statik arayüzde bu
uçlar kullanılıyordu; React'e geçişte (Faz 1) hiç taşınmadı. Bu, oturum
boyunca tekrar eden bir desenin son örneği: backend hazır, frontend eksik.

Ayrıca şu an gerçek bir operasyonel boşluk var: SMTP bilgileri hâlâ örnek
değerlerde (`lisans@sirketiniz.com`, boş şifre) ve bunu değiştirecek bir
arayüz yok — mail gönderimi bu yüzden hiç çalışmıyor. Bu modül bu boşluğu
kapatıyor.

## Netleştirilen kararlar (kullanıcıyla doğrulandı)

- Kapsamdaki bölümler: **SMTP ayarları, Logo bağlantı ayarları, Hesap
  bilgisi, Otomatik senkron zamanlaması** (dördü de istendi).
- **Yerleşim**: Rol seçim ekranında ("Nasıl devam etmek istersiniz?"),
  Yönetici Girişi / Satış ve Muhasebe dairelerinin altında, ortada küçük
  bir "Ayarlar" bağlantısı. Ne Yönetici ne Satış paneline bağlı — üçüncü,
  bağımsız bir giriş noktası. Gerçek bir rol/yetki sistemi olmadığı için
  (Faz 1 spec'inde netleştirildi: tek paylaşılan giriş, rol seçimi salt
  istemci tarafı görünüm tercihi) bu basit ve tutarlı.
- **Otomatik senkron anahtarı gerçekten işlevsel olacak.** Şu an
  `logo_auto_sync` ayarı kaydediliyor ama `scheduler.py` ona hiç bakmıyor —
  senkron günde 3 kez (11/15/17) koşulsuz çalışıyor. Bu modülle birlikte
  anahtar gerçekten senkronu açıp kapatacak.
- **Şifre alanları düz metin kalacak** (bilinen, kabul edilmiş sınırlama —
  `settings` tablosunda zaten öyle duruyor, `license_reminders.db`
  gitignore'da). Form alanlarında `type="password"` kullanılır (ekranda
  maskelenir) ama mevcut değer önceden doldurulur — değiştirmeden
  kaydedilirse aynı değer geri gönderilir, sorun değil.

## Mimari

### Yönlendirme (`App.tsx`)

Mevcut `Step` tipine (`'checking' | 'login' | 'role-select' | 'transition' |
'panel'`) `'settings'` eklenir. `RoleSelectPage`'e yeni bir `onOpenSettings:
() => void` prop'u eklenir; bağlantıya tıklanınca `step` `'settings'`e
geçer. `SettingsPage`'in `onBack` prop'u `step`'i `'role-select'`e
döndürür. Giriş/rol/panel akışının geri kalanı değişmez.

### Bileşen yapısı

```
frontend/src/
  pages/
    RoleSelectPage.tsx    # değişecek: alt kısımda "Ayarlar" bağlantısı
    SettingsPage.tsx      # yeni: sayfa iskeleti (başlık, geri butonu, 4 kart)
  components/settings/
    SmtpSettingsCard.tsx      # yeni
    LogoSettingsCard.tsx      # yeni
    AccountSettingsCard.tsx   # yeni
    SyncScheduleCard.tsx      # yeni
  lib/
    api.ts                 # eklenecek: getSettings zaten var (ReminderModal
                            # kullanıyor), updateSettings(), updateAccount(),
                            # sendTestEmail(), testLogoConnection(),
                            # triggerLogoSync()
```

Her kart bağımsız: kendi form state'ini tutar, kendi kaydet/test
butonlarına sahiptir, kendi başarı/hata mesajını gösterir. Biri
kaydedilirken diğerleri etkilenmez — `ReminderModal`/`NewOfferModal`'daki
"kendi state'ini yöneten kart" deseniyle tutarlı.

### Veri akışı

1. `SettingsPage` açılırken tek bir `GET /api/settings` çağrılır
   (`Record<string, string>` döner — backend zaten böyle). Sonuç 4 karta
   prop olarak dağıtılır.
2. Her kart `POST /api/settings` ile **yalnızca kendi alanlarını** içeren
   bir body gönderir (backend `body_data.items()` üzerinde upsert yaptığı
   için bu güvenli — gönderilmeyen anahtarlara dokunulmaz).
3. `AccountSettingsCard` ayrı uç kullanır: `POST /api/account`
   (`current_password`, `new_username`, `new_password`). Mevcut şifre
   yanlışsa backend `401` + `"Mevcut şifre hatalı."` döner, kart bunu
   olduğu gibi gösterir.
4. `SmtpSettingsCard`'daki "Test E-postası Gönder" → `POST /api/test-email`
   (opsiyonel `recipients`, boşsa backend `internal_recipients`
   ayarındakilere gönderir).
5. `LogoSettingsCard`'daki "Bağlantıyı Test Et" → `POST
   /api/logo/test-connection`. "Şimdi Senkronize Et" → `POST
   /api/logo/sync` (backend zaten var, üç senkronu sırayla çalıştırıp
   özet mesaj döndürüyor).
6. `SyncScheduleCard`: `logo_auto_sync` değerini `'ON'`/`'OFF'` olarak
   gösteren bir anahtar (toggle), `POST /api/settings` ile kaydedilir.

### Backend değişikliği: otomatik senkron anahtarını işlevsel yap

`scheduler.py:logo_sync_loop()` şu an saat kontrolünden hemen sonra
senkronu koşulsuz çalıştırıyor. Değişiklik: senkron çalışmadan hemen önce
`get_logo_settings()['logo_auto_sync']` okunur; değer `'OFF'` ise o
döngü adımı (o saatteki senkron) atlanır ama `calisan_saatler` yine de
işaretlenir (aksi halde her 60 saniyelik kontrolde tekrar tekrar
"atlandı" loglanır). Varsayılan değer hâlâ `'OFF'` (mevcut default) —
yani bu değişiklik canlıya çıktığı an senkron **durur**; kullanıcı
Ayarlar'dan açana kadar. Bu, spec onayından sonra kullanıcıyla açıkça
teyit edilecek bir davranış değişikliği (bkz. Test bölümü).

## Hata Yönetimi

Her kart kendi hata yolunu yönetir, mevcut modallerdeki desenle aynı:
ağ hatasında genel "Sunucuya ulaşılamıyor" mesajı, backend'in döndürdüğü
`{success, message}` şekli olduğu gibi gösterilir. `AccountSettingsCard`
özel olarak: yanlış mevcut şifre, boş yeni şifre (opsiyonel, göndermezse
şifre değişmez) durumlarını ayrı ayrı ele alır.

## Kapsam Dışı

- Yönetici Analiz Dashboard'u ve Sistem Tespitleri Widget'ı — Faz 3'ün
  sıradaki alt-projeleri, ayrı spec.
- Şifrelerin veritabanında şifrelenmesi — bilinen, kasıtlı olarak
  ertelenen bir sınırlama.
- `logo_auto_sync` için saat listesini (`LOGO_SYNC_SAATLERI`)
  özelleştirme — kod sabiti olarak kalıyor, ayar değil.
- Gerçek çoklu kullanıcı/rol yetkilendirmesi (Faz 1'de zaten reddedildi).

## Test

Faz 1/2 ile tutarlı: otomatik test paketi yok. Manuel QA ile: 4 kartın
her biri ayrı ayrı kaydedilip `GET /api/settings`'in güncellendiğini
doğrulama; SMTP test maili (SMTP bilgileri gerçek girildiğinde) hem
başarı hem hata yolunu; Logo bağlantı testi; hesap şifre değişikliği
sonrası çıkış yapıp yeni bilgiyle giriş; otomatik senkron anahtarını
kapatıp `scheduler.py` loglarında o saatte senkronun atlandığını
gözlemleme.
