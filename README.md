# Yurt İnterneti İzleme, Ön Tanı ve Raporlama

Zabbix'ten gelen firewall verisini dakikada bir çekip:

- **tüm yurtları tek tabloda** gösterir (dakikada bir yenilenir),
- arıza anında **otomatik ön tanı** koyar (muhtemel sebep + önerilen aksiyon + uzaktan çözülür mü),
- **e-posta ile bildirim** gönderir (aynı arıza için tekrar tekrar değil),
- her hafta **özet rapor** yollar (en sorunlu yurtlar, kesinti süreleri, hat doluluğu).

## Mevcut ortam

| | |
|---|---|
| Zabbix | 7.4.12 — `https://zabbix.piramit.com.tr` |
| Kapsam | 34 yurt, host grubu `Tugva-Firewall` |
| Cihazlar | WatchGuard Firebox (M / T / XTM serisi) |
| Şablon | `Network Generic Device by SNMP` |

## Kurulum

```bash
pip install -r requirements.txt
```

`config.yaml` hazır ve çalışır durumda. Yeni bir ortama taşırken
`config.example.yaml` dosyasını şablon olarak kullanın.

Gizli bilgileri dosyaya yazmak istemezseniz ortam değişkeni de kullanılabilir:
`YURTNET_ZABBIX_TOKEN`, `YURTNET_SMTP_USERNAME`, `YURTNET_SMTP_PASSWORD`,
`YURTNET_DASHBOARD_PASSWORD`.

### Sunucuya kurulum

Ubuntu Server 24.04 üzerinde systemd servisi olarak çalışır; sunucu yeniden
başlasa da kendi ayağa kalkar. Adım adım: **[deploy/KURULUM.md](deploy/KURULUM.md)**

## Komutlar

| Komut | İşlev |
|---|---|
| `python -m yurtnet.main` | Sürekli çalışır; dakikada bir kontrol, dashboard'u yayınlar |
| `python -m yurtnet.main --once` | Tek tur çalıştır ve çık |
| `python -m yurtnet.main --check` | Zabbix bağlantısını ve bölge eşlemesini doğrula |
| `python -m yurtnet.main --dump` | Zabbix envanterini `envanter.txt`'ye dök |
| `python -m yurtnet.main --test-mail` | SMTP ayarlarını test et |
| `python -m yurtnet.main --report-now` | Haftalık raporu hemen gönder |
| `python -m yurtnet.main -v` | Ayrıntılı log |

Dashboard: `http://<sunucu>:8787/` — kullanıcı adı/parola `config.yaml > dashboard.auth`

## Dashboard erişimi

Giriş, ortak bir kullanıcı adı/parola ile yapılan bir form üzerinden. Başarılı
girişte imzalı bir oturum çerezi verilir (`session_days`, varsayılan 7 gün),
sağ üstteki "Çıkış yap" ile sonlandırılabilir. İmza anahtarı `.session_secret`
dosyasında saklandığı için uygulama yeniden başladığında kimse düşmez.

Tabloda yurtların public IP adresleri göründüğü için, ağa açık bir dashboard
(`bind` değeri `127.0.0.1` dışında) parolasız çalıştırılamaz — uygulama başlamayı
reddeder. Parola düz metin olarak taşındığından makine şirket iç ağında kalmalı,
internete açılmamalı.

## Bu ortama özgü çözülmüş üç konu

**1. Bölge bilgisi.** Zabbix'te bölge etiketi tanımlı değil. Bölge, host adındaki
il adından türetiliyor (`TUGVA-TRABZON-M300` → Trabzon → Karadeniz). 34 yurdun
34'ü eşleşiyor, İstanbul ilçeleri (Florya, Güngören, Üsküdar) dahil.
Zabbix'e ileride `bolge` etiketi eklenirse o öncelikli olur, koda dokunmak gerekmez.

**2. WAN bacağı.** Her cihazda farklı (eth0, eth2, eth4, eth5, eth6, eth7…).
Trafik yönünden otomatik bulunuyor: indirmenin göndermeden baskın olduğu,
en çok trafik alan fiziksel arayüz WAN kabul edilir. Yanlış seçtiği bir yurt
olursa `config.yaml > wan.interfaces` altında elle verilebilir.

**3. Hat kapasitesi.** `net.if.speed` işe yaramaz — fiziksel port hızını
(1 Gbps) verir, ISP'den alınan hattı değil. ISP hızları bilinmediği için
`bandwidth.mode: learned` kullanılıyor: araç trafiği kaydeder, 7 gün veri
biriktikten sonra her yurdun tepe trafiğine bakıp en yakın standart abonelik
basamağına yuvarlar. O ana kadar doluluk sütunu boş kalır; diğer her şey çalışır.
Gerçek hızlar öğrenilirse `bandwidth.per_host` altına yazılır ve tahmini ezer.

## Kontrol sıklığı

Zabbix'teki item'ların hepsi **1 dakika** aralıklı güncelleniyor (ping, kayıp,
gecikme, trafik, arayüz durumu). Bundan daha sık sormak aynı değeri tekrar
okumak olur, o yüzden `check_interval_minutes: 1` bu kurulum için en hızlı
anlamlı ayardır. Bir tur ~5 saniye sürer.

Tablo da dakikada bir yenilenir. Yenileme sırasında arama kutusuna yazdığınız
metin, bölge/durum filtreleri ve kaydırma konumu korunur; ayrıca aktif olarak
yazıyorsanız yenileme ertelenir.

## Ön tanı kuralları

Kurallar öncelik sırasına göre denenir; ilki ana tanı, kalanlar ek bulgu olur.

| Kod | Ne zaman | Ne anlama gelir |
|---|---|---|
| `NO_DATA` | Hiç ölçüm gelmiyor | Cihaz kapalı / hat komple kopuk |
| `HOST_DOWN` | ICMP ping başarısız | İnternet kopuk |
| `WAN_IFACE_DOWN` | WAN arayüzü down | Kablo/SFP veya ISP portu kapanmış |
| `WAN_SILENT` | Cihaz ayakta, WAN trafiği ~0 | ISP tarafı kopuk, PPPoE düşmüş |
| `PACKET_LOSS` | Kayıp > eşik | Hat kalitesi / SFP / omurga |
| `SATURATION` | Doluluk > eşik | Arıza değil, **kapasite** sorunu |
| `HIGH_LATENCY` | Gecikme > eşik | Doluluk veya ISP rota sorunu |
| `REBOOTED` | Çalışma süresi < 20 dk | Elektrik kesintisi / kilitlenme / firmware |
| `IF_ERRORS` | Hata/discard > 0 | Fiziksel katman (kablo, SFP, duplex) |
| `FLAPPING` | 1 saatte N kez inip kalkma | Güç / hat kalitesi — yerinde müdahale |
| `STALE_DATA` | Veri var ama bayat | İzleme akışı tıkalı |
| `NO_IF_DATA` | Ping var, SNMP arayüz verisi yok | İzleme eksiği (arıza değil) |
| `REGIONAL_OUTAGE` | Aynı bölgede N+ yurt kopuk | ISP/omurga kesintisi — sahaya çıkmadan teyit alın |
| `PLANNED_DOWN` | Elle işaretlenmiş | Bilinçli kapatma — arıza değil, hesaba katılmaz |

## Bilinçli kapatma

Yaz döneminde boş kalan yurtlarda internet kasıtlı olarak kapatılıyor. Bu
durumdaki yurtlar hafta boyu "kritik arıza" olarak görünüp erişilebilirlik
oranını yanlış biçimde düşürür.

Tabloda erişilemeyen bir yurdun satırında **"Bilinçli kapalı"** düğmesi çıkar;
isteğe bağlı bir sebep yazıp basmanız yeterli. O andan itibaren:

- Yurt kritik arıza yerine "Bilinçli kapalı" (bilgi) olarak görünür
- Erişilebilirlik hesabına ve arıza kayıtlarına girmez, mail gönderilmez
- **Süregelen kesinti geçmişe dönük de düzeltilir** — yurdun en son ayakta
  görüldüğü ana kadar geri gidilir, o penceredeki kayıtlar temizlenir.
  Daha eski, ilgisiz kesintilere dokunulmaz.

Yurt yeniden ping'e cevap vermeye başladığında **işaret kendiliğinden kalkar**.
Bu kasıtlıdır: yazın işaretlenip unutulan bir yurtta sonbaharda çıkan gerçek
arızanın gizlenmesini önler.

Yanlışlıkla işaretlerseniz aynı satırdaki "Arıza olarak işaretle" düğmesi geri alır.

`HIGH_CPU` / `HIGH_MEMORY` kuralları da var ama bu filoda tetiklenmez:
generic SNMP şablonu WatchGuard'ın CPU/bellek OID'lerini içermiyor.

Eşikler `config.yaml > thresholds` altında.

## Mail gürültüsünü kısan üç mekanizma

1. **`email.min_severity`** — altındaki bulgular maillenmez (`info` seviyesindekiler
   sadece tabloda görünür).
2. **`email.alert_cooldown_minutes`** — aynı arıza için bu süre dolmadan tekrar mail gitmez.
3. **Bölgesel bastırma** — bir bölgede toplu kesinti varsa tekil "kopuk" mailleri
   bastırılır, tek bölgesel uyarı gider.

Arıza kapanınca tek bir "düzeldi" özeti gönderilir.

## Bilinen izleme eksikleri (Zabbix tarafı)

Bunlar aracın değil, mevcut Zabbix kurulumunun eksikleri:

- **`TUGVA-SIVAS-T35`** — cihaz SNMP'ye hiç cevap vermiyor. WatchGuard'da SNMP
  servisi kapalı ya da Zabbix sunucusunun IP'sine izin veren politika yok.
- **`TUGVA-KAYSERI-XTM330`, `TUGVA-TRABZON-M300`** — filodaki tek SNMPv3 host'ları
  (diğer 32'si SNMPv2). Arayüz keşfi saatte bir çalışıyor.

Bu üç yurtta ping/kayıp/gecikme tabanlı tespit tam çalışır; sadece trafik ve
doluluk ölçülemez.

## Dosya düzeni

```
yurtnet/
  config.py     yapılandırma yükleme ve doğrulama
  zabbix.py     Zabbix JSON-RPC istemcisi (5.0–7.x)
  regions.py    host adı -> il -> coğrafi bölge
  inventory.py  --dump envanter dökümü
  collect.py    ham item verisi -> yurt bazlı ölçüm (arayüz ayrıştırma, WAN seçimi)
  diagnose.py   ön tanı kuralları
  store.py      SQLite: ölçüm geçmişi, arıza kayıtları, kapasite öğrenme
  notify.py     e-posta bildirimleri
  dashboard.py  HTML tablo + HTTP sunucu
  report.py     haftalık rapor
  main.py       zamanlayıcı ve CLI
config.yaml     çalışan ayarlar (token içerir — paylaşmayın)
envanter.txt    son Zabbix envanter dökümü
yurtnet.db      SQLite veritabanı
```

```
deploy/
  KURULUM.md      Ubuntu 24.04 kurulum adımları
  yurtnet.service systemd servis tanımı
```

## Sonraki adımlar

- SMTP bilgileri girilip `email.enabled: true` yapılacak
- Ubuntu 24 sunucusuna taşıma + systemd servisi
- Gerçek ISP hat hızları öğrenildikçe `bandwidth.per_host` doldurulacak
