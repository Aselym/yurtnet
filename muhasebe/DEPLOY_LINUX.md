# Kurulum: Linux Sunucuya Dağıtım

Windows tarafı için [DEPLOY.md](DEPLOY.md) geçerli kalmaya devam ediyor — bu
dosya aynı uygulamayı bir **Linux sunucuya** (Debian/Ubuntu) kurmak için.

Logo ERP bağlantısı (lisans/fatura verisi) sadece şirket LAN'ından erişilebilen
bir MS SQL sunucusuna gittiği için (`192.168.0.20`), sunucu **şirket ağı
içinde** olmalı — ya fiziksel/sanal bir LAN makinesi, ya da şirket LAN'ına
VPN ile bağlı bir sunucu. Salt genel internete açık bir VPS'e taşımak Logo
bağlantısını koparır.

## Otomatik kurulum (önerilen)

Hedef sunucuda `muhasebe` klasöründen:

```bash
sudo ./deploy_linux.sh --logo
```

Bu tek komut: dosyaları `/opt/piramit-muhasebe`'ye kopyalar, ayrı bir
`piramit-muhasebe` sistem kullanıcısı oluşturur (uygulama root olarak
çalışmaz), bir Python venv kurup bağımlılıkları (Logo bağlantısı için
`pyodbc`) yükler, ufw/firewalld varsa `5000` portunu açar, ve bir **systemd
servisi** kaydedip başlatır — sunucu yeniden başlasa bile kendiliğinden
ayağa kalkar.

Logo bağlantısı gerekmiyorsa `--logo` bayrağını vermeden çalıştırabilirsiniz.

Diğer seçenekler:
```bash
sudo ./deploy_linux.sh --dir /opt/piramit-muhasebe --port 5000 --user piramit-muhasebe --logo
```

### Masaüstü bildirimi Linux'ta hiç görünmez — bu beklenen davranış

`send_windows_toast()` Windows'a özgü bir API kullanıyor (`notifier.py`);
Linux'ta artık hiçbir şey yapmadan sessizce çıkıyor (hata basmıyor). Bu bir
eksiklik değil — bir sunucuda zaten kimse interaktif masaüstü oturumu açık
tutmuyor. Esas hatırlatma zaten iç ekibe **mail** ile gidiyor, bildirim
sadece Windows PC kurulumlarında bonus bir özellikti.

### Logo bağlantısı için ek bir adım var: ODBC sürücüsü

`pyodbc` Python paketi Linux'ta çalışmak için sistemde kurulu bir **ODBC
sürücüsüne** ihtiyaç duyar (Windows'ta bu, işletim sistemiyle gelir).
`--logo` bayrağı `unixodbc`'yi kurar ama asıl SQL Server sürücüsünü
Microsoft'un kendi deposundan ayrıca kurmanız gerekiyor:

```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo tee /etc/apt/trusted.gpg.d/microsoft.asc
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

(Ubuntu sürümünüze göre `22.04` kısmını değiştirin — güncel talimat:
https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server)

`logo_sync.py` sürücüyü otomatik seçiyor (önce 18, sonra 17) — kurulumdan
sonra ek bir ayar gerekmez, Ayarlar sekmesinden Logo bağlantısını test
etmeniz yeterli.

## Kalan tek adım: IP'yi sabitleyin

Ekip `http://<sunucu-ip>:5000` ile bağlanacak. Bu IP zaman zaman değişebiliyorsa
IT'nin bu sunucu için bir **statik IP ya da DHCP rezervasyonu** ayarlaması
gerekir, yoksa adres değiştiğinde ekip yanlış adrese bakar.

## Test

```bash
sudo systemctl status piramit-muhasebe
```

`active (running)` görmelisiniz. Sonra başka bir bilgisayardan tarayıcıyla
`http://<sunucu-ip>:5000` adresine gidip giriş yapabilmelisiniz.

## Günlük işletim

```bash
sudo systemctl restart piramit-muhasebe   # yeniden başlat
sudo systemctl stop piramit-muhasebe      # durdur
sudo journalctl -u piramit-muhasebe -f    # canlı log takibi
```

Kod güncellemesi geldiğinde (`app.py`, `scheduler.py` vb. değişince) dosyaları
tekrar sunucuya kopyalayıp servisi yeniden başlatmanız yeterli — en güvenlisi
`deploy_linux.sh`'i tekrar çalıştırmak, mevcut veritabanına dokunmaz.

## Manuel kurulum (deploy_linux.sh kullanmadan)

<details>
<summary>Adım adım elle kurulum</summary>

### 1. Gereksinimler
```bash
sudo apt-get install -y python3 python3-venv python3-pip
# Logo bağlantısı gerekiyorsa:
sudo apt-get install -y unixodbc unixodbc-dev
# + yukarıdaki "ODBC sürücüsü" adımındaki msodbcsql18 kurulumu
```

### 2. Klasörü kopyala
Bu `muhasebe` klasörünü sunucuya kopyalayın (örn. `/opt/piramit-muhasebe`).

### 3. Sanal ortam ve bağımlılıklar
```bash
cd /opt/piramit-muhasebe
python3 -m venv venv
venv/bin/pip install -r requirements.txt   # pyodbc (Logo) + openpyxl (Excel çıktısı)
```

### 4. LAN'dan erişime aç
```bash
sudo ufw allow 5000/tcp        # ufw kullanıyorsanız
# veya
sudo firewall-cmd --permanent --add-port=5000/tcp && sudo firewall-cmd --reload
```

### 5. systemd servisi
`/etc/systemd/system/piramit-muhasebe.service` dosyasını oluşturun:

```ini
[Unit]
Description=Piramit Muhasebe - Lisans Takip Uygulamasi
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=piramit-muhasebe
WorkingDirectory=/opt/piramit-muhasebe
ExecStart=/opt/piramit-muhasebe/venv/bin/python /opt/piramit-muhasebe/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now piramit-muhasebe
```

</details>
