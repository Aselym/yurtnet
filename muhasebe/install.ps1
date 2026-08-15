#Requires -RunAsAdministrator
<#
    Piramit Muhasebe - Lisans Takip Uygulamasi kurulum betigi.

    Bu betik, USB bellekteki `muhasebe` klasorunun icinden calistirilir.
    Hedef bilgisayara kopyalar, firewall kuralini acar ve Task Scheduler'a
    "oturum acilista otomatik baslat" gorevini ekler.

    Kullanim (yonetici PowerShell):
        .\install.ps1
        .\install.ps1 -HedefKlasor "D:\PiramitMuhasebe" -Port 5000 -LogoSurucusuKur
#>

param(
    [string]$HedefKlasor = "C:\PiramitMuhasebe",
    [int]$Port = 5000,
    [switch]$LogoSurucusuKur
)

$ErrorActionPreference = "Stop"
$KaynakKlasor = $PSScriptRoot

function Yaz-Adim($mesaj) {
    Write-Host ""
    Write-Host "== $mesaj ==" -ForegroundColor Cyan
}

# ---------------------------------------------------------------- 1. Python
Yaz-Adim "1/5 Python kontrolu"

$PythonExe = @(
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1)
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $PythonExe) {
    Write-Host "Python bulunamadi. Once https://www.python.org/downloads/ adresinden" -ForegroundColor Red
    Write-Host "Python 3.10+ kurun ('Add python.exe to PATH' isaretli olsun), sonra bu betigi tekrar calistirin." -ForegroundColor Red
    exit 1
}
Write-Host "Python bulundu: $PythonExe" -ForegroundColor Green

# ---------------------------------------------------------------- 2. Kopyala
Yaz-Adim "2/5 Dosyalar $HedefKlasor konumuna kopyalaniyor"

if ($KaynakKlasor -ieq $HedefKlasor) {
    Write-Host "Kaynak ve hedef ayni, kopyalama atlaniyor." -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Force -Path $HedefKlasor | Out-Null

    # Var olan veritabani ve ayarlar korunur; kod dosyalari uzerine yazilir.
    $HaricTut = @('license_reminders.db', '__pycache__', '*.pyc', '.git', 'install.ps1')
    Get-ChildItem -Path $KaynakKlasor -Force | Where-Object {
        $ad = $_.Name
        -not ($HaricTut | Where-Object { $ad -like $_ })
    } | ForEach-Object {
        Copy-Item -Path $_.FullName -Destination $HedefKlasor -Recurse -Force
    }
    Write-Host "Kopyalandi." -ForegroundColor Green
}

# ---------------------------------------------------------------- 3. Bagimliliklar
Yaz-Adim "3/5 Python bagimliliklari"

if ($LogoSurucusuKur) {
    Write-Host "Logo ERP baglantisi icin pyodbc kuruluyor..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r "$HedefKlasor\requirements.txt"
    Write-Host "NOT: 'ODBC Driver 17/18 for SQL Server' ayrica Microsoft'tan kurulmali (Logo baglantisi icin)." -ForegroundColor Yellow
} else {
    Write-Host "Atlandi (Logo baglantisi gerekmiyorsa gerek yok). Gerekirse: .\install.ps1 -LogoSurucusuKur" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- 4. Firewall
Yaz-Adim "4/5 Firewall kurali (port $Port)"

$KuralAdi = "Piramit Muhasebe"
if (Get-NetFirewallRule -DisplayName $KuralAdi -ErrorAction SilentlyContinue) {
    Write-Host "Kural zaten var, atlandi." -ForegroundColor DarkGray
} else {
    New-NetFirewallRule -DisplayName $KuralAdi -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow | Out-Null
    Write-Host "Kural eklendi." -ForegroundColor Green
}

# ---------------------------------------------------------------- 5. Otomatik baslatma
Yaz-Adim "5/5 Oturum acilista otomatik baslatma (Task Scheduler)"

$GorevAdi = "Piramit Muhasebe"
$VbsYolu = Join-Path $HedefKlasor "start_hidden.vbs"

if (Get-ScheduledTask -TaskName $GorevAdi -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $GorevAdi -Confirm:$false
}

$Eylem  = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsYolu`""
$Tetik  = New-ScheduledTaskTrigger -AtLogOn
$Ayarlar = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# Interactive logon ile calismali: SYSTEM hesabinda calisirsa masaustu
# bildirimi (send_windows_toast) hic gorunmez.
$Sahip = "$env:USERDOMAIN\$env:USERNAME"
$Prensip = New-ScheduledTaskPrincipal -UserId $Sahip -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $GorevAdi -Action $Eylem -Trigger $Tetik -Settings $Ayarlar -Principal $Prensip -Description "Piramit Muhasebe lisans takip uygulamasini oturum acilista arka planda baslatir." | Out-Null

Write-Host "Gorev eklendi." -ForegroundColor Green

# ---------------------------------------------------------------- Bitis
Yaz-Adim "Kurulum tamamlandi"

Write-Host "Uygulamayi simdi test etmek icin baslatiliyor..." -ForegroundColor Cyan
Start-Process "wscript.exe" -ArgumentList "`"$VbsYolu`""
Start-Sleep -Seconds 3
Write-Host "Birkac saniye icinde sag altta 'Uygulama calisiyor' bildirimi cikmali." -ForegroundColor Cyan
Write-Host "Tarayicidan http://localhost:$Port adresine gidip giris yapabilirsiniz." -ForegroundColor Cyan
Write-Host ""
Write-Host "Bilgisayari yeniden baslatinca da otomatik acilacak (Task Scheduler: '$GorevAdi')." -ForegroundColor DarkGray
