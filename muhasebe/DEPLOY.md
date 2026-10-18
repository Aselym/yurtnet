# Kurulum: 7/24 Erişim İçin Sunucuya Dağıtım

Logo ERP bağlantısı (lisans/fatura verisi) sadece şirket LAN'ından erişilebilen
bir MS SQL sunucusuna gittiği için (`192.168.0.20`), bu uygulama buluta/VPS'e
taşınamaz — mutlaka **şirket ağındaki, hep açık kalan bir Windows makinesine**
kurulmalı.

## Otomatik kurulum (önerilen)

Hedef sunucuda **yönetici PowerShell** açıp `muhasebe` klasöründen:

```powershell
.\install.ps1 -LogoSurucusuKur -SunucuModu
```

Bu tek komut: dosyaları `C:\PiramitMuhasebe`'ye kopyalar, Logo bağlantısı için
`pyodbc`'yi kurar, Windows Firewall'da 5000 portunu açar, ve **sunucu
açılışında (kimse oturum açmasa bile) otomatik başlayan** bir Task Scheduler
görevi kaydeder.

`-SunucuModu` bayrağının bedeli: masaüstü bildirimi (`send_windows_toast`)
hiç görünmez — SYSTEM hesabının masaüstü oturumu olmadığı için. Bu bir kayıp
değil, esas hatırlatma zaten iç ekibe **mail** ile gidiyor; bildirim sadece
bonus bir özellikti. (Sunucuda birisi sürekli oturum açık tutacaksa ve
bildirimi de görmek istiyorsanız `-SunucuModu` vermeden çalıştırın — o zaman
"kullanıcı oturum açınca başlat" moduna döner.)

## Kalan tek adım: IP'yi sabitleyin

Ekip `http://<sunucu-ip>:5000` ile bağlanacak. Bu IP, router'dan DHCP ile
geliyorsa zaman zaman değişebilir — IT'nin bu sunucu için bir **DHCP
rezervasyonu ya da statik IP** ayarlaması gerekir, yoksa adres değiştiğinde
ekip yanlış adrese bakar.

## Test

Sunucuyu yeniden başlatıp birkaç saniye bekleyin, sonra başka bir bilgisayardan
tarayıcıyla `http://<sunucu-ip>:5000` adresine gidip giriş yapabilmelisiniz.

## Manuel kurulum (install.ps1 kullanmadan)

<details>
<summary>Adım adım elle kurulum</summary>

### 1. Gereksinimler
- Python 3.10+ kurulu olmalı (`pythonw.exe` de python ile birlikte gelir, ayrıca kurulum gerektirmez).
- Gerekli: `pip install -r requirements.txt` (openpyxl → Excel çıktısı, pyodbc → Logo bağlantısı). Logo için ayrıca "ODBC Driver 17/18 for SQL Server".

### 2. Klasörü kopyala
Bu `muhasebe` klasörünü sunucuya kopyalayın (örn. `C:\PiramitMuhasebe`).

### 3. LAN'dan erişime aç (Windows Firewall)
```powershell
New-NetFirewallRule -DisplayName "Piramit Muhasebe" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

### 4. Sunucu açılışında otomatik başlatma (Task Scheduler)
1. **Task Scheduler** → **Create Task**
2. **General**: İsim verin (örn. "Piramit Muhasebe"), **"Run whether user is logged on or not"** işaretleyin.
3. **Triggers** → **New** → **"At startup"** seçin.
4. **Actions** → **New** → Program: klasördeki `start_hidden.vbs` dosyasının tam yolu (örn. `C:\PiramitMuhasebe\start_hidden.vbs`).
5. **General**'a dönüp "Change User or Group" ile `SYSTEM` seçin (ya da özel bir servis hesabı).
6. Kaydedin.

</details>
