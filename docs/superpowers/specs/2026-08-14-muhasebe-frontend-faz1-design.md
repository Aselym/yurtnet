# Muhasebe Frontend Yeniden Tasarımı — Faz 1: Giriş ve Yönlendirme

## Bağlam ve Amaç

Piramit Bilgisayar'ın iç muhasebe/lisans takip uygulaması (`muhasebe/`) şu an
Python `http.server` üzerinde saf HTML/CSS/JS ile çalışıyor
(`muhasebe/static/index.html`, `app.js`, `styles.css`). Arayüz işlevsel ama
sade; hedef, kurumsal bir SaaS ürünü kalitesinde, "premium" hissettiren bir
deneyime geçmek.

Talep 3 fazlık bir yeniden tasarım: Faz 1 (Giriş + Rol Seçimi), Faz 2
(Satış/Muhasebe operasyon ekranı), Faz 3 (Yönetici analiz ekranı). Bu spec
**yalnızca Faz 1**'i kapsar; her faz kendi tasarım/onay döngüsünden geçecek.

## Mimari Kararlar

- **Toolchain:** Yeni `muhasebe/frontend/` klasöründe Vite + React + TypeScript
  + Tailwind CSS + Framer Motion + shadcn/ui. Mevcut Python backend'den tamamen
  ayrı bir geliştirme ortamı; backend'e yeni bir runtime bağımlılığı eklemiyor.
- **Deploy stratejisi:** Build yalnızca geliştirme makinesinde çalıştırılır
  (`npm run build`). Hedef bilgisayara (muhasebe PC'si) **Node.js kurulmaz** —
  sadece derlenmiş statik çıktı gönderilir. `DEPLOY.md` / `install.ps1`
  değişmez, hâlâ yalnızca Python gerektirir.
- **Build çıktısı hedefi:** `vite.config.ts` içinde `outDir: '../static'`,
  `base: '/static/'`. Backend'deki [do_GET](../../../muhasebe/app.py) zaten
  `/`, `/login`, `/dashboard` isteklerinde `static/index.html`'i, `/static/*`
  isteklerinde `static/` altındaki dosyaları serve ediyor — route değişikliği
  gerekmiyor.
- **Backend'de gereken tek dokunuş:** `do_GET`'teki MIME türü eşlemesi şu an
  yalnızca `.css/.js/.png/.svg/.jpg` biliyor. Vite çıktısındaki `.woff2`,
  `.json`, `.map` uzantıları için eşleme eklenecek (aksi halde yanlış
  content-type ile servis edilir ve fontlar/haritalar bozulur).
- **Fontlar:** Inter, CDN yerine Vite ile bundle edilerek self-host edilecek —
  internet kesintisinde arayüz bozulmasın diye.
- **Renk paleti:** Mevcut `styles.css`'teki marka tokenleri aynen taşınır:
  `--brand: #f2691f` (turuncu) ve açık/koyu tema paletinin tamamı. Yeni renk
  icat edilmiyor, marka tutarlılığı korunuyor.
- **Rol modeli:** Backend'de tek kullanıcı adı/şifre var, gerçek rol/yetki
  sistemi yok. "Yönetici Girişi" / "Satış ve Muhasebe" seçimi **backend'e
  gitmeyen, salt istemci tarafı bir görünüm seçimi**. Faz 1 bu yüzden
  backend'de auth/rol değişikliği gerektirmiyor.

## Bileşen Yapısı

```
frontend/
  src/
    pages/
      LoginPage.tsx        # kullanıcı adı/şifre formu
      RoleSelectPage.tsx   # iki dairesel buton + Framer Motion giriş animasyonu
      LoadingTransition.tsx# 3 saniyelik marka temalı geçiş ekranı
      PlaceholderPanel.tsx # rol bazlı iskelet panel ("Faz 2/3 yapım aşamasında")
    lib/
      auth.ts              # mevcut /api/login, /api/check-auth, /api/logout çağrıları
    components/ui/         # shadcn bileşenleri (button, card, input...)
    App.tsx                # router + auth durumu
```

Faz 2/3 henüz yok, bu yüzden rol seçiminden sonra geçici bir iskelet panel
açılır ("Yönetici Paneli — Faz 2'de geliyor" gibi). Faz 1 böylece tek başına
çalışır durumda teslim edilir; sonraki fazlarda bu iskeletler gerçek
panellerle değişir.

## Veri Akışı

1. Uygulama açılışında `GET /api/check-auth` çağrılır (mevcut endpoint,
   değişmiyor). Oturum geçerliyse login ekranı atlanır.
2. Giriş: `POST /api/login` — backend zaten `HttpOnly` çerez basıyor, React
   tarafı yalnızca başarı/hata durumunu yönetir.
3. Rol seçimi backend'e gitmez, `sessionStorage`'a yazılır (`piramit.rol`) —
   sayfa yenilense bile o oturumda hatırlanır.
4. Role tıklama → 3 saniyelik `LoadingTransition` (marka renklerinde, şık,
   sahte ama akışkan) → ilgili iskelet panele Framer Motion ile pürüzsüz
   geçiş (fade/scale).
5. Çıkış: mevcut `POST /api/logout` + `sessionStorage` temizliği, login
   ekranına döner.

## Hata Yönetimi

- Yanlış kullanıcı adı/şifre → backend'in döndüğü mesaj, formun üstünde bir
  hata bandı olarak gösterilir (mevcut `login-error` mantığının React
  karşılığı).
- Sunucuya ulaşılamıyorsa (network hatası) → genel bir "Sunucuya
  ulaşılamıyor" bildirimi; kullanıcı formu tekrar deneyebilir.
- `check-auth` isteği başarısız olursa güvenli taraf seçilir: oturum yokmuş
  gibi davranılıp login ekranı gösterilir.

## Test

Küçük bir iç araç olduğu için Faz 1'de otomatik test paketi kurulmuyor.
Doğrulama Browser preview ile elle yapılır: giriş akışı, rol seçimi, loading
animasyonu, açık/koyu tema, mobil genişlik. İleride kritik akışlara
(auth gibi) Vitest smoke test eklenebilir — Faz 1 kapsamı dışında.

## Kapsam Dışı (sonraki fazlar)

- Faz 2: Satış/Muhasebe operasyon ekranı, mail otomasyonu modalı, Kanban
  teklif panosu.
- Faz 3: Yönetici analiz dashboard'u, sahte "sistem tespitleri" widget'ı,
  ayarlar modülü.
- Gerçek çoklu kullanıcı/rol tabanlı yetkilendirme (şu an reddedildi, sadece
  görünüm seçimi yapılacak).
