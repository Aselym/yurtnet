# yurtnet — kurulum haritası

Bu belge **ne yapılacağını ve hangi sırayla** anlatır. Komutların tamamı
[KURULUM.md](KURULUM.md) içindedir; burada adım adım komut yoktur, plan vardır.

Toplam süre: bilgiler hazırsa **yarım gün**. Uzatan tek şey, aşağıdaki
"önceden halledilmesi gerekenler" kısmıdır — bunlar başkasından cevap
beklediği için kurulum gününe bırakılırsa iş bir haftaya yayılır.

---

## Kurulunca ortaya çıkacak yapı

```
                    ┌──────────────────────────┐
                    │  zabbix.piramit.com.tr   │   ölçümün kaynağı
                    │  (mevcut Zabbix 7.4.12)  │   — dokunulmuyor
                    └────────────┬─────────────┘
                                 │ HTTPS / API (dışarı doğru)
                                 │ her dakika 34 yurt sorgulanır
   ┌─────────────────────────────┴──────────────────────────────┐
   │  VERİ MERKEZİ — Ubuntu Server 26.04 VM                     │
   │                                                            │
   │   nginx :443 ──► yurtnet :8787 (yalnız 127.0.0.1)          │
   │   (TLS + Let's Encrypt)         │                          │
   │                                 ├── yurtnet.db  (SQLite)   │
   │                                 └── systemd ile 7/24       │
   └──────┬──────────────────────────────────────┬──────────────┘
          │ HTTPS                                │ SMTP :465
          ▼                                      ▼
  yurtnet.piramit.com.tr                  Mail sunucusu
  ├─ /        pano (ekip)         ├─ arıza + düzeldi bildirimi
  ├─ /ekran   TÜGVA'daki TV       └─ her ayın 1'i PDF rapor
  └─ /ayarlar mail ayarları
```

**Üç dış bağımlılık var:** Zabbix API'si, mail sunucusu, DNS. Üçü de bizim
kontrolümüzde değil — bu yüzden aşama 0 var.

---

## Aşama 0 — Önceden halledilmesi gerekenler

Kurulum gününden **önce** bitmiş olmalı. Hepsi başka birinden cevap bekliyor.

| # | İş | Kimden | Neden erken |
|---|---|---|---|
| 0.1 | VM açılması (Ubuntu Server 26.04, 2 CPU / 2 GB / 40 GB SSD, genel IP) | Veri merkezi | Kurulumun zemini |
| 0.2 | SSH erişimi (anahtarla) | Veri merkezi | Bunsuz hiçbir şey yapılamaz |
| 0.3 | **Giden 465/TCP portunun açılması** | Veri merkezi | Barındırma firmaları giden SMTP'yi varsayılan olarak kapatır; açtırmak birkaç gün sürebilir |
| 0.4 | Yeni mail hesabı: adres, sunucu, port, parola | Sizden / sistem yöneticisi | **Engelleyici değil** — panodan sonradan girilebilir, ama mail olmadan bildirim de yok |
| 0.5 | Zabbix'in veri merkezi IP'sine izin vermesi | Zabbix yöneticisi | Sunucuda IP kısıtı varsa token doğru olsa bile bağlanılamaz |
| 0.6 | `yurtnet.piramit.com.tr` A kaydı | DNS'i yöneten kişi | Yayılması saatler alır; sertifika buna bağlı |

**Aşama 0 bitmeden aşama 1'e başlamayın.** Özellikle 0.3 ve 0.6 beklemeyi
sever; ikisi de "istedik, cevap bekliyoruz" durumuna erken düşsün.

### Kurulum öncesi doğrulama

VM açılır açılmaz, tek satırlık üç kontrol (komutlar KURULUM.md §0'da):

- Zabbix API'si cevap veriyor mu → `apiinfo.version` → `7.4.12` dönmeli
- Mail sunucusuna 465 açık mı → `nc -zv`
- VM'in dış IP'si ne → DNS kaydına bu yazılacak

Üçü de yeşilse devam. Değilse aşama 0'a geri dönün — ileride çözmek daha pahalı.

---

## Aşama 1 ve 2 — Tek betikle kurulum

Sunucu hazırlığı ile uygulama kurulumunun tamamını `deploy/kur.sh` yapar:
saat dilimi (`Europe/Istanbul`), paketler (**`fonts-dejavu-core`** dâhil),
`yurtnet` kullanıcısı, dosyalar, sanal ortam, systemd servisi. Aynı komut
tekrar çalıştırılabilir — `config.yaml` ve `yurtnet.db` varsa üzerine yazmaz,
bu yüzden güncelleme için de kullanılır.

Adım adım komutlar ve iki taşıma yöntemi (SSH / USB) için
**`kurulum-paketi/OKU-BENI.md`** dosyasına bakın; elle karşılıkları ve
ayrıntılı açıklama KURULUM.md §1–§7'de.

Özet:

```bash
sudo bash /tmp/yurtnet-kurulum/deploy/kur.sh
sudo cp /tmp/yurtnet-kurulum/config.sunucu.yaml /opt/yurtnet/config.yaml
cd /opt/yurtnet && sudo -u yurtnet .venv/bin/python -m yurtnet.main --check
sudo systemctl start yurtnet
```

`--check` **34 yurt ve bölge dağılımını** listelemeli. Hata varsa servise
geçmeyin; log içinde aramaktan kolaydır.

## Aşama 3 — Mail

> Panodaki **⚙ Ayarlar** sayfası · KURULUM.md §8

Mail bilgileri artık `config.yaml`'dan değil, panonun içindeki Ayarlar
sayfasından giriliyor. Bu yüzden **mail hesabı hazır olmadan da kuruluma
başlanabilir**: uygulama açılır, mail gönderimi kapalı başlar, sayfa eksikleri
gösterir. Hesap hazır olunca panodan doldurulur, servisi yeniden başlatmaya
gerek kalmaz.

Sayfada üç bölüm var: **mail hesabı** (SMTP), **yönetici raporu alıcıları**
(aylık PDF) ve **teknik servis alıcıları** (arıza + düzeldi bildirimi +
haftalık teknik rapor).

Doğrulama:

1. "Kaydet ve test maili gönder" → sonuç ekranda görünür.
2. `--monthly-now` → PDF ekli aylık rapor. **Eki açıp Türkçe harfleri
   kontrol edin**; bozuksa DejaVu kurulmamıştır.
3. Elle tetikleme o ayki otomatik gönderimi "yapıldı" sayar. Ayın 1'inden
   önce test ettiyseniz `job_runs` kaydını silin, yoksa ilk otomatik rapor
   gitmez.

> Denemeyi önce yalnız kendinize yapın: `monthly_recipients` listesini
> geçici olarak tek adrese indirin, sonra geri açın.

## Aşama 4 — Alan adı ve HTTPS

> KURULUM.md §9

1. A kaydının yayıldığını doğrulayın: `dig +short yurtnet.piramit.com.tr`
2. nginx ters vekil bloğu. **`X-Forwarded-Proto` başlığı şart** — onsuz
   uygulama isteği HTTP sanar ve oturum çerezine `Secure` koymaz.
3. `certbot --nginx -d yurtnet.piramit.com.tr`, 80→443 yönlendirmesini
   kabul edin. Sertifika kendini yeniler.
4. `public_url`'i `https://...` yapıp servisi yeniden başlatın.

## Aşama 5 — Ekran modu (TÜGVA merkezindeki televizyon)

> KURULUM.md §11

Duvara asılacak ekran `/ekran` adresini açar. Menüsüz, filtresiz, uzaktan
okunacak boyda; sorunlu yurtlar üstte büyük kartlar, 34 yurdun tamamı altta
renkli ızgarada. Sağ üstteki saat her saniye ilerler ve veri bayatlarsa
kırmızıya döner — donmuş bir ekran fark edilmeden kalmasın.

Ekran tarafında yalnız bir mini PC gerekir, Chromium kiosk modunda. **TÜGVA
ağında hiçbir kurulum yok** — VPN yok, ajan yok. Bir kez giriş yapılır, oturum
süresiz olduğu için bir daha parola sorulmaz.

## Aşama 6 — Kapatma ve devreye alma

> KURULUM.md §10–§11

1. Güvenlik duvarı: yalnız **22, 80, 443**. 8787 dışarı açılmaz.
2. SSH parola girişini kapatın (`PasswordAuthentication no`).
3. **Windows'taki kopyada `email.enabled: false` yapın.** Açık kalırsa aynı
   arıza için hem sunucudan hem sizin makinenizden mail gider.
4. Ekibe duyurun: pano adresi, ekran adresi, kullanıcı adı, parola.

## Aşama 7 — Sonrası

| Konu | Nasıl |
|---|---|
| Kod güncelleme | Windows'ta `.\deploy\yukle.ps1 -Sunucu <ip> -Kullanici <ssh>` — config, veritabanı ve oturumlara dokunmaz |
| Ayar değişikliği | Sunucuda `config.yaml` + `systemctl restart yurtnet` |
| Yedek | Tek gereken: `yurtnet.db` ve `config.yaml` |
| Disk | Ölçümler ~2 MB/gün; 90 günlük saklamada ~180 MB |
| Log | `journalctl -u yurtnet -f` |

---

## Bu kurulumda kolayca gözden kaçanlar

Hepsi bu projede bilfiil yaşandı ya da yaşanmaya çok yakındı:

1. **Saat dilimi UTC kalırsa** her şey 3 saat kayar, üstelik hata vermez.
2. **DejaVu fontu yoksa** PDF sessizce bozuk Türkçe üretir.
3. **Giden 465 kapalıysa** mail hiç gitmez; uygulama "gönderilemedi" yazar
   ama kimse logu okumaz.
4. **`X-Forwarded-Proto` unutulursa** HTTPS'te oturum çerezi güvensiz kalır.
5. **Kod değişince servis yeniden başlatılmazsa** eski sürüm çalışmaya devam
   eder; dosyayı düzeltip "neden değişmedi" diye aranır.
6. **Windows kopyasında mail açık kalırsa** her arıza iki kez maillenir.

---

## Şu an bekleyen tek bilgi

**Yeni mail hesabı**: adres, sunucu adı, port. Bu netleşmeden aşama 3
tamamlanamaz ve aşama 0.3'teki port talebi de doğru sunucu için açılamaz.
