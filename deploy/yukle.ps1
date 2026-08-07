# yurtnet — sunucuya kod gönderme betiği
#
# Kullanım:
#   .\deploy\yukle.ps1 -Sunucu 10.0.0.5 -Kullanici hakan
#   .\deploy\yukle.ps1 -Sunucu 10.0.0.5 -Kullanici hakan -SadeceGoster   # ne kopyalanacak, sadece listeler
#
# Yalnızca KOD gönderilir. Sunucudaki şu dosyalara asla dokunulmaz:
#   config.yaml         (parolalar ve sunucuya özgü ayarlar orada)
#   mail_ayarlari.json  (panodaki Ayarlar sayfasından girilen mail bilgileri)
#   yurtnet.db        (tüm ölçüm geçmişi ve arıza kayıtları)
#   .session_secret   (açık oturumlar düşmesin diye)
#   raporlar/         (üretilmiş rapor arşivi)

param(
    [Parameter(Mandatory = $true)][string]$Sunucu,
    [Parameter(Mandatory = $true)][string]$Kullanici,
    [string]$Hedef = "/opt/yurtnet",
    [switch]$SadeceGoster
)

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path $PSScriptRoot -Parent)

# Gönderilecek kod dosyaları
$dosyalar = @(
    "yurtnet",
    "deploy",
    "requirements.txt",
    "README.md",
    "config.example.yaml"
)

Write-Output "Gonderilecek:"
foreach ($d in $dosyalar) {
    if (Test-Path $d) { Write-Output "   $d" }
    else { Write-Output "   $d  (YOK - atlanacak)" }
}
Write-Output ""
Write-Output "Hedef: $Kullanici@$Sunucu`:$Hedef"

if ($SadeceGoster) { Write-Output "`n(SadeceGoster: hicbir sey kopyalanmadi)"; exit 0 }

$gecici = "/tmp/yurtnet-yukleme"

Write-Output "`n[1/4] Gecici dizin hazirlaniyor..."
ssh "$Kullanici@$Sunucu" "rm -rf $gecici && mkdir -p $gecici"

Write-Output "[2/4] Dosyalar kopyalaniyor..."
$mevcut = $dosyalar | Where-Object { Test-Path $_ }
scp -r -q $mevcut "$Kullanici@$Sunucu`:$gecici/"

Write-Output "[3/4] Yerine tasiniyor..."
# __pycache__ temizlenir: eski .pyc dosyalari silinen modulleri diri tutabiliyor.
$komut = @"
sudo rm -rf $Hedef/yurtnet/__pycache__ &&
sudo cp -r $gecici/* $Hedef/ &&
sudo chown -R yurtnet:yurtnet $Hedef &&
sudo chmod 600 $Hedef/config.yaml $Hedef/mail_ayarlari.json 2>/dev/null;
rm -rf $gecici
"@
ssh "$Kullanici@$Sunucu" $komut.Replace("`r`n", " ")

Write-Output "[4/4] Servis yeniden baslatiliyor..."
ssh "$Kullanici@$Sunucu" "sudo systemctl restart yurtnet && sleep 4 && systemctl is-active yurtnet"

Write-Output "`nSon loglar:"
ssh "$Kullanici@$Sunucu" "journalctl -u yurtnet -n 8 --no-pager -o cat"

Write-Output "`nTamamlandi."
