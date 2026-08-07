#!/usr/bin/env bash
# yurtnet — Ubuntu Server 26.04 kurulum betiği
#
# Kullanım (sunucuda, dosyalar /tmp/yurtnet-kurulum içine kopyalandıktan sonra):
#   sudo bash /tmp/yurtnet-kurulum/deploy/kur.sh
#
# Aynı komutu tekrar çalıştırmak güvenlidir: var olanı bozmaz, eksikleri
# tamamlar. config.yaml ve yurtnet.db varsa ASLA üzerine yazılmaz.

set -euo pipefail

HEDEF=/opt/yurtnet
KULLANICI=yurtnet
KAYNAK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bu betik root ile çalıştırılmalı:  sudo bash $0" >&2
    exit 1
fi

adim() { echo; echo "==> $*"; }

# ---------------------------------------------------------------- 1. saat dilimi
adim "Saat dilimi"
MEVCUT_TZ="$(timedatectl show -p Timezone --value)"
if [ "$MEVCUT_TZ" != "Europe/Istanbul" ]; then
    # Veri merkezi sunucuları UTC gelir. yurtnet baştan sona yerel saate göre
    # çalışır: günlük grafiklerin gün sınırları, raporlardaki saatler ve aylık
    # raporun gönderim saati. UTC kalırsa her şey 3 saat kayar, üstelik sessizce.
    timedatectl set-timezone Europe/Istanbul
    echo "    $MEVCUT_TZ -> Europe/Istanbul"
else
    echo "    zaten Europe/Istanbul"
fi

# ---------------------------------------------------------------- 2. paketler
adim "Paketler"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# fonts-dejavu-core isteğe bağlı DEĞİL: PDF raporundaki Türkçe karakterler
# onsuz bozulur ve bunu hata vermeden yapar.
apt-get install -y -qq python3 python3-venv python3-pip rsync sqlite3 fonts-dejavu-core
echo "    tamam"

# ---------------------------------------------------------------- 3. kullanıcı
adim "Kullanıcı ve dizin"
if ! id -u "$KULLANICI" >/dev/null 2>&1; then
    useradd --system --home "$HEDEF" --shell /usr/sbin/nologin "$KULLANICI"
    echo "    $KULLANICI kullanıcısı oluşturuldu"
else
    echo "    $KULLANICI zaten var"
fi
mkdir -p "$HEDEF"

# ---------------------------------------------------------------- 4. dosyalar
adim "Kod kopyalanıyor"
for parca in yurtnet deploy requirements.txt README.md config.example.yaml; do
    [ -e "$KAYNAK/$parca" ] && cp -r "$KAYNAK/$parca" "$HEDEF/"
done
rm -rf "$HEDEF/yurtnet/__pycache__"

# config.yaml varsa dokunulmaz: sunucudaki ayarlar ve parolalar orada.
if [ ! -f "$HEDEF/config.yaml" ]; then
    cp "$HEDEF/config.example.yaml" "$HEDEF/config.yaml"
    echo "    config.yaml örnekten oluşturuldu — DÜZENLENMESİ GEREKİYOR"
    YENI_CONFIG=1
else
    echo "    config.yaml korundu"
    YENI_CONFIG=0
fi

chown -R "$KULLANICI:$KULLANICI" "$HEDEF"
chmod 600 "$HEDEF/config.yaml"
[ -f "$HEDEF/mail_ayarlari.json" ] && chmod 600 "$HEDEF/mail_ayarlari.json"

# ---------------------------------------------------------------- 5. python
adim "Python ortamı"
if [ ! -x "$HEDEF/.venv/bin/python" ]; then
    sudo -u "$KULLANICI" python3 -m venv "$HEDEF/.venv"
fi
sudo -u "$KULLANICI" "$HEDEF/.venv/bin/pip" install -q --upgrade pip
sudo -u "$KULLANICI" "$HEDEF/.venv/bin/pip" install -q -r "$HEDEF/requirements.txt"
echo "    $("$HEDEF/.venv/bin/python" --version)"

# ---------------------------------------------------------------- 6. servis
adim "systemd servisi"
cp "$HEDEF/deploy/yurtnet.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable yurtnet >/dev/null 2>&1
echo "    kuruldu (henüz başlatılmadı)"

# ---------------------------------------------------------------- son
echo
echo "──────────────────────────────────────────────────────────────"
if [ "$YENI_CONFIG" -eq 1 ]; then
    cat <<'SON'
Kurulum tamam. SIRADAKİ ADIMLAR:

  1) Ayarları doldurun (Zabbix token'ı ve pano parolası):
       sudo nano /opt/yurtnet/config.yaml

  2) Bağlantıyı doğrulayın — 34 yurt listelenmeli:
       cd /opt/yurtnet && sudo -u yurtnet .venv/bin/python -m yurtnet.main --check

  3) Servisi başlatın:
       sudo systemctl start yurtnet
       journalctl -u yurtnet -f

  4) Mail ayarlarını panodaki ⚙ Ayarlar sayfasından girin.

  5) Alan adı ve HTTPS için: deploy/KURULUM.md §9
SON
else
    cat <<'SON'
Güncelleme tamam. Servisi yeniden başlatın:

       sudo systemctl restart yurtnet
       journalctl -u yurtnet -f
SON
fi
echo "──────────────────────────────────────────────────────────────"
