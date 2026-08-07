# Ubuntu Server 26.04'e kurulum

Sırayla uygulayın. Tamamı 10-15 dakika sürer.

## 0. Sanal makine

| | |
|---|---|
| İşletim sistemi | Ubuntu Server 26.04 LTS (masaüstü sürümü değil) |
| CPU | 2 çekirdek (uygulama tek çekirdeğin ~%1'ini kullanıyor) |
| RAM | 2 GB (uygulama ~50 MB; gerisi işletim sistemi ve nginx için) |
| Disk | 40 GB SSD (veritabanı ~2 MB/gün, 90 günde ~190 MB'de sabitlenir) |
| Ağ | `zabbix.piramit.com.tr` adresine HTTPS (443) erişimi olmalı |
| Ağ | Mail sunucusuna 465/TCP çıkışı olmalı (aylık rapor ve arıza bildirimi) |
| Saat dilimi | `Europe/Istanbul` (bkz. §1) |

### Veri merkezine kuruyorsanız

Kuruluma başlamadan **üç şeyi doğrulayın**; üçü de sonradan fark edilirse
kurulumu geri almanız gerekir:

```bash
# 1. Zabbix API'sine ulaşılıyor mu (sunucu tarafında IP kısıtı olabilir)
curl -sS -X POST https://zabbix.piramit.com.tr/api_jsonrpc.php \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"apiinfo.version","params":{},"id":1}'
# Beklenen: {"jsonrpc":"2.0","result":"7.4.12","id":1}

# 2. Mail sunucusuna 465 çıkışı açık mı
#    Barındırma firmalarının çoğu giden SMTP portlarını varsayılan olarak
#    kapatır; kapalıysa sağlayıcıdan açılmasını talep edin.
nc -zv <mail-sunucusu> 465

# 3. Sunucunun dış IP'si (DNS A kaydı buna bakacak)
curl -s https://ifconfig.me
```

Sağlayıcının güvenlik grubunda (VM'in kendi `ufw`'undan ayrı) yalnız
**22, 80, 443** açılmalı. Uygulamanın portu 8787 dışarı **açılmaz**.

Kurulum sırasında **OpenSSH sunucusunu** işaretleyin, yoksa uzaktan bağlanamazsınız.

VM'e sabit bir IP verin — hem ekip hem de alan adının DNS kaydı bu adrese bakacak.

## 1. Gerekli paketler

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip rsync fonts-dejavu-core
```

Kurulum sonrası `python3 --version` ile sürümü teyit edin. yurtnet
**Python 3.10 ve üzerinde** çalışır; 26.04'ün getirdiği sürüm bunu
fazlasıyla karşılar. Kod ayrıca 3.14'te de geliştirilip test edildi.

### Saat dilimi — atlanırsa her şey 3 saat kayar

Veri merkezi sunucuları çoğunlukla **UTC** ile kurulu gelir. yurtnet baştan
sona yerel saate göre çalışır: günlük kesinti grafiğinin gün sınırları,
raporlardaki saatler, aylık raporun gönderim saati. UTC kalırsa grafikler
yanlış güne düşer ve "her ayın 1'i saat 09:00" gönderimi 12:00'de olur.

```bash
timedatectl set-timezone Europe/Istanbul
timedatectl        # Time zone: Europe/Istanbul (+03) yazmalı
```

Bunu **veritabanı oluşmadan önce** yapın. Sonradan değiştirirseniz eski
ölçümlerin gün kırılımı kayar (kayıtlar UTC saklandığı için veri kaybolmaz,
sadece geçmiş grafiklerde gün sınırı bir kez kayar).

**`fonts-dejavu-core` isteğe bağlı değil.** Aylık rapor PDF'i Türkçe karakter
içeriyor ve fpdf2'nin yerleşik fontu Latin-1'dir; "ı ş ğ İ" harfleri bozulur.
Kod sırayla Arial (Windows), DejaVu, Liberation arar — sunucuda bu paket yoksa
PDF bozuk üretilir ama hata vermez, yani fark edilmesi zordur.

Alan adıyla yayına alacaksanız (bkz. §9) şunlar da gerekir:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

## 2. Kullanıcı ve dizin

Araç kendi kullanıcısıyla çalışsın — sorun çıkarsa sistemin geri kalanına
dokunamaz. `--system` ile giriş yapılamayan bir hesap oluşturulur.

```bash
sudo useradd --system --home /opt/yurtnet --shell /usr/sbin/nologin yurtnet
sudo mkdir -p /opt/yurtnet
```

## 3. Dosyaları kopyalayın

Windows makinede, proje klasöründen (`C:\Claude 1`):

```bash
scp -r yurtnet deploy requirements.txt README.md config.yaml <kullanici>@<vm-ip>:/tmp/yurtnet-kurulum/
```

VM'de:

```bash
sudo cp -r /tmp/yurtnet-kurulum/* /opt/yurtnet/
sudo chown -R yurtnet:yurtnet /opt/yurtnet
rm -rf /tmp/yurtnet-kurulum
```

> `config.yaml` API token ve parola içerir. Kopyaladıktan sonra izinlerini kısın:
> ```bash
> sudo chmod 600 /opt/yurtnet/config.yaml
> ```

## 4. Python ortamı

```bash
sudo -u yurtnet python3 -m venv /opt/yurtnet/.venv
sudo -u yurtnet /opt/yurtnet/.venv/bin/pip install -r /opt/yurtnet/requirements.txt
```

## 5. Ayarları sunucuya göre düzenleyin

```bash
sudo -u yurtnet nano /opt/yurtnet/config.yaml
```

Sunucuda değişmesi gereken alanlar:

```yaml
dashboard:
  # Nginx kullanacaksanız 127.0.0.1 bırakın: uygulama yalnız yerelden dinler,
  # dışarıya nginx açılır. Nginx yoksa 0.0.0.0 yapın.
  bind: "127.0.0.1"
  # Maillerdeki bağlantı buradan üretilir. VM'in IP'si değil, dışarıdan
  # açılabilen gerçek adres yazılmalı.
  public_url: "https://yurtnet.piramit.com.tr"

email:
  enabled: true
  smtp_host: "<yeni mail sunucusu>"
  username: "<yeni hesap>"
  sender: "<yeni hesap>"
  recipients:                 # arıza bildirimi gidecek adresler
    - "..."

report:
  monthly_recipients:         # her ayın 1'inde PDF raporu gidecek adresler
    - "yonetici@ornek.com.tr"
    - "ikinci@ornek.com.tr"
```

`bind` değeri `127.0.0.1` dışında olduğunda parola zorunlu hale gelir;
`dashboard.auth.password` dolu olduğu için sorun çıkmaz. Boş bırakılırsa
uygulama bilerek başlamaz.

Parolaları dosyada tutmak istemezseniz `/etc/yurtnet.env` kullanın (bkz. en alt).

## 6. Bağlantıyı doğrulayın

```bash
cd /opt/yurtnet
sudo -u yurtnet .venv/bin/python -m yurtnet.main --check
```

34 yurt ve bölge dağılımı listelenmeli. Hata alırsanız servise geçmeden önce
burayı çözün — sorunu servis loglarında aramaktan daha kolay.

## 7. Servisi kurun

```bash
sudo cp /opt/yurtnet/deploy/yurtnet.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yurtnet
systemctl status yurtnet
```

`active (running)` görmelisiniz. Canlı log:

```bash
journalctl -u yurtnet -f
```

Beklenen çıktı: her dakika `Tur bitti: 34 yurt, N bulgu ...`

## 8. Mail gönderimini doğrulayın

```bash
cd /opt/yurtnet
sudo -u yurtnet .venv/bin/python -m yurtnet.main --test-mail
```

Test maili geldiyse aylık raporu da bir kez elle tetikleyip ekteki PDF'i açın —
Türkçe karakterler bozuksa `fonts-dejavu-core` kurulmamış demektir:

```bash
sudo -u yurtnet .venv/bin/python -m yurtnet.main --monthly-now
```

> Bu komut gerçek alıcılara mail gönderir. Denemeyi önce yalnız kendinize
> yapmak isterseniz `config.yaml` içindeki `report.monthly_recipients`
> listesini geçici olarak tek adrese indirin.

Elle tetikleme, o ayki otomatik gönderimi de "yapıldı" sayar (aynı rapor iki kez
gitmesin diye). Ayın 1'inden önce test ettiyseniz kaydı silin:

```bash
sudo -u yurtnet sqlite3 /opt/yurtnet/yurtnet.db \
  "DELETE FROM job_runs WHERE job='monthly_report';"
```

## 9. Alan adı ve HTTPS

Pano internete açılacaksa **HTTPS zorunludur**: giriş parolası düz HTTP'de
şifresiz gider. Uygulama TLS konuşmaz, önüne nginx konur.

**a) DNS kaydı.** `piramit.com.tr` bölgesine bir A kaydı ekleyin:

```
yurtnet.piramit.com.tr.   A   <sunucunun-dış-ip-adresi>
```

Veri merkezindeki VM'in kendi genel IP'si varsa doğrudan onu yazın
(`curl -s https://ifconfig.me` ile öğrenilir). Sunucu NAT arkasındaysa kayıt
şirketin dış IP'sine bakar ve firewall'da 80/443 bu VM'e yönlendirilir.

> Certbot sertifikayı alabilmek için 80 portundan sunucuya ulaşmak zorundadır.
> DNS yayılmadan veya 80 kapalıyken çalıştırırsanız hata verir; bu normaldir,
> DNS oturduktan sonra tekrar deneyin (`dig +short yurtnet.piramit.com.tr`).

**b) Nginx.** `/etc/nginx/sites-available/yurtnet` dosyasını oluşturun:

```nginx
server {
    listen 80;
    server_name yurtnet.piramit.com.tr;

    location / {
        proxy_pass http://127.0.0.1:8787;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        # Bu başlık olmadan uygulama isteği HTTP sanır ve oturum çerezine
        # Secure bayrağını koymaz.
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/yurtnet /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**c) Sertifika.** DNS yayıldıktan sonra:

```bash
sudo certbot --nginx -d yurtnet.piramit.com.tr
```

Certbot 80'i 443'e yönlendirmeyi teklif eder; **kabul edin**. Sertifika kendini
otomatik yeniler, ek bir iş gerekmez.

**d) config.yaml.** `public_url` değerini `https://yurtnet.piramit.com.tr`
yapın ve servisi yeniden başlatın.

## 10. Güvenlik duvarı

Nginx ile (dışarı açık kurulum):

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

Uygulamanın kendi portu (8787) **dışarı açılmamalı** — `bind: 127.0.0.1`
olduğu için zaten dinlemez.

Nginx olmadan, yalnız şirket iç ağına açacaksanız:

```bash
sudo ufw allow from 192.168.0.0/16 to any port 8787 proto tcp
```

Tabloda yurtların IP adresleri göründüğü için portu parolasız/şifresiz biçimde
internete açmayın.

### Panel internete açıksa

Veri merkezi kurulumunda pano dünyaya açık olur. İki şey şart:

- **HTTPS** (§9). Düz HTTP'de giriş parolası ağda açık gider.
- **SSH parola girişini kapatın.** `/etc/ssh/sshd_config` içinde
  `PasswordAuthentication no` yapıp anahtarla girin; internete açık 22
  portu sürekli kaba kuvvet denemesi alır.

Giriş denemeleri `journalctl -u yurtnet | grep "giriş denemesi"` ile görülür —
uygulama başarısız denemeyi kaynak IP'siyle loglar ve 0,7 sn geciktirir.

## 11. Ekran modu (televizyona yansıtma)

Duvara asılacak ekran için ayrı bir sayfa var: `/ekran`. Panodaki üst çubukta
**Ekran** bağlantısından da açılır.

**İki slayt hâlinde, 10 saniyede bir kayarak geçer.** Tıklanınca da ilerler.
Sayfa her dakika kendini yenilerken hangi slaytta olduğu korunur.

| Slayt | İçerik |
|---|---|
| 1 | Durum özeti: 4 KPI kartı, sorunlu yurtlar büyük kartlar hâlinde, 34 yurdun tamamı renkli ızgarada |
| 2 | 34 yurdun **eth1** trafiği — her yurt için ayrı mini grafik, son 3 saat |

İkinci slayttaki grafikler her yurt kendi ölçeğinde çizilir ve tepe değeri
yanına yazılır; ortak ölçek kullanılsaydı küçük yurtlar düz çizgi görünürdü.
Veri Zabbix geçmişinden gelir ve 3 dakika önbellekte tutulur — ekran her dakika
yeniden çiziliyor, 60 item'lık sorguyu her seferinde tekrarlamanın görsel bir
faydası yok. SNMP arayüz keşfi eksik olan yurtlarda "veri yok" yazar.

Normal panodan farkı: menü, filtre ve düğme yok; yazılar 3-4 metreden okunacak
boyda. İmleç gizlidir, fare oynatılınca 3 saniyeliğine görünür.

**Saat neden büyük:** duvardaki bir ekranın en tehlikeli hâli sessizce
donmasıdır — kimse fark etmez, herkes eski veriye bakar. Sağ üstteki saat her
saniye ilerler; veri bayatlarsa (sunucu veya ağ durduysa) saat kırmızıya döner.

### Ekran tarafındaki kurulum

Ekrana bağlı bir mini PC yeterli. Chromium kiosk modunda açılışta başlatın:

```bash
chromium --kiosk --noerrdialogs --disable-infobars \
         --incognito=false https://yurtnet.piramit.com.tr/ekran
```

İlk açılışta bir kez kullanıcı adı/parola sorar. `session_days: 0` olduğu için
bir daha sormaz — oturum süresiz. (Bu ayar bilerek böyle: süre dolsaydı ekran
giriş sayfasına düşer ve başında kimse olmadığı için öyle kalırdı.)

Akıllı TV'nin kendi tarayıcısı da iş görür ama güvenilmez; mini PC daha sağlam.

## 12. Ekibe duyurun

```
Pano   : https://yurtnet.piramit.com.tr/
Ekran  : https://yurtnet.piramit.com.tr/ekran
Kullanıcı adı : yurtnet
Parola : (config.yaml içindeki değer)
```

---

## Sonrası: geliştirme akışı

Kurulumdan sonra kod iki yerde bulunur: geliştirme yaptığınız Windows makinesi
ve sunucu. Karışmaması için ayrım nettir:

| | Windows (`C:\Claude 1`) | Sunucu (`/opt/yurtnet`) |
|---|---|---|
| Rolü | Geliştirme ve test | Gerçek çalışan sistem |
| E-posta | **Kapalı** | Açık |
| Dashboard | `127.0.0.1` | `0.0.0.0` |
| Veritabanı | Test verisi | Gerçek geçmiş |

**Kod göndermek** (Windows'ta, proje kökünden):

```powershell
.\deploy\yukle.ps1 -Sunucu <vm-ip> -Kullanici <ssh-kullanici>
```

Betik yalnızca kodu gönderir, servisi yeniden başlatır ve son logları gösterir.
Sunucudaki `config.yaml`, `yurtnet.db`, `.session_secret` ve `raporlar/`
dizinine **dokunmaz** — ayarlar, geçmiş ve açık oturumlar korunur.

Ne gideceğini önce görmek için:

```powershell
.\deploy\yukle.ps1 -Sunucu <vm-ip> -Kullanici <ssh-kullanici> -SadeceGoster
```

> **Windows'taki kopyada e-postayı kapalı tutun** (`email.enabled: false`).
> Açık kalırsa aynı arıza için hem sunucudan hem sizin makinenizden mail gider.
> `yukle.ps1` config dosyasını kopyalamadığı için bu ayar sunucuya taşınmaz.

**Ayar değişikliği** (parola, alıcı listesi, eşik) sunucuda yapılır:

```bash
sudo -u yurtnet nano /opt/yurtnet/config.yaml
sudo systemctl restart yurtnet
```

Kod güncellemesinden sonra servis yeniden başlar ama **oturumlar düşmez** —
imza anahtarı `.session_secret` dosyasında kalıcıdır, ekip yeniden giriş yapmaz.

**Yedekleme:** Yedeklenmesi gereken tek şey `/opt/yurtnet/yurtnet.db`
(tüm ölçüm geçmişi ve arıza kayıtları) ve `config.yaml`.

**Mail hesabı değiştiğinde:** `config.yaml` içindeki `email` bölümünde
`smtp_host`, `smtp_port`, `username`, `password`, `sender` alanlarını
güncelleyin. Port 465 doğrudan SSL demektir (`use_ssl: true`, `use_tls: false`);
587 kullanılacaksa tersi (`use_ssl: false`, `use_tls: true`). Ardından test edin:

```bash
sudo -u yurtnet /opt/yurtnet/.venv/bin/python -m yurtnet.main --test-mail
sudo systemctl restart yurtnet
```

Parolayı dosyada tutmak istemezseniz `/etc/yurtnet.env` içine yazın —
servis dosyası bu dosyayı okuyacak şekilde ayarlı:

```
YURTNET_SMTP_PASSWORD=...
YURTNET_DASHBOARD_PASSWORD=...
```

```bash
sudo chmod 600 /etc/yurtnet.env
```

## Sorun giderme

| Belirti | Bakılacak yer |
|---|---|
| Servis başlamıyor | `journalctl -u yurtnet -n 50` — çoğunlukla yapılandırma hatası, mesaj açık yazar |
| Dashboard açılmıyor | `sudo ss -tlnp \| grep 8787` port dinleniyor mu; sonra `ufw status` |
| Zabbix'e bağlanamıyor | VM'den `curl -sI https://zabbix.piramit.com.tr` |
| Tablo güncellenmiyor | `journalctl -u yurtnet -f` ile tur logları akıyor mu |
