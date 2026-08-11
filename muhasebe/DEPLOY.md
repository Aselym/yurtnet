# Kurulum: Sürekli Açık Kalacak PC'ye Dağıtım

## 1. Gereksinimler
- Python 3.10+ kurulu olmalı (`pythonw.exe` de python ile birlikte gelir, ayrıca kurulum gerektirmez).
- İsteğe bağlı: Logo bağlantısı için `pip install -r requirements.txt` (pyodbc) ve "ODBC Driver 17/18 for SQL Server".

## 2. Klasörü kopyala
Bu `muhasebe` klasörünü, mesai saatlerinde sürekli açık kalacak PC'ye kopyalayın (örn. `C:\PiramitMuhasebe`).

## 3. LAN'dan erişime aç (Windows Firewall)
PowerShell'i yönetici olarak açıp:

```powershell
New-NetFirewallRule -DisplayName "Piramit Muhasebe" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow
```

Diğer bilgisayarlardan `http://<bu-pc-nin-ip-adresi>:5000` ile erişilebilir hale gelir.

## 4. Bilgisayar açılışında otomatik başlatma (Task Scheduler)
1. **Task Scheduler**'ı açın → **Create Task**
2. **General** sekmesi: İsim verin (örn. "Piramit Muhasebe"), **"Run whether user is logged on or not"** seçmeyin — masaüstü bildirimleri için kullanıcı oturumu açık olmalı, bu yüzden normal "Run only when user is logged on" kalsın.
3. **Triggers** sekmesi → **New** → **"At log on"** seçin (belirli kullanıcı ya da herhangi bir kullanıcı).
4. **Actions** sekmesi → **New** → Program: klasördeki `start_hidden.vbs` dosyasının tam yolunu seçin (örn. `C:\PiramitMuhasebe\start_hidden.vbs`).
5. Kaydedin. Bir sonraki açılışta uygulama arka planda (konsol penceresi olmadan) otomatik başlayacak ve "Uygulama çalışıyor" bildirimini gösterecektir.

## 5. Test
Bilgisayarı yeniden başlatıp giriş yapın, birkaç saniye içinde sağ altta "Piramit Muhasebe: Uygulama çalışıyor" bildirimi çıkmalı. Tarayıcıdan `http://localhost:5000` adresine gidip giriş yapabilirsiniz.
