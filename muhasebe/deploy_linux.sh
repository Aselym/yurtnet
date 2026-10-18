#!/usr/bin/env bash
#
# Piramit Muhasebe - Lisans Takip Uygulamasi Linux kurulum betigi.
#
# install.ps1'in Linux karsiligi: dosyalari hedef klasore kopyalar, bir
# Python venv kurar, systemd servisi olusturup baslatir, firewall'da portu
# acar. Debian/Ubuntu (apt) icin yazildi.
#
# Kullanim (sudo ile):
#   sudo ./deploy_linux.sh
#   sudo ./deploy_linux.sh --logo --dir /opt/piramit-muhasebe --port 5000
#
set -euo pipefail

HEDEF_KLASOR="/opt/piramit-muhasebe"
PORT=5000
LOGO_KUR=0
SERVIS_KULLANICI="piramit-muhasebe"

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) HEDEF_KLASOR="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --logo) LOGO_KUR=1; shift ;;
    --user) SERVIS_KULLANICI="$2"; shift 2 ;;
    -h|--help)
      echo "Kullanim: $0 [--dir /opt/piramit-muhasebe] [--port 5000] [--logo] [--user piramit-muhasebe]"
      exit 0
      ;;
    *)
      echo "Bilinmeyen parametre: $1" >&2
      exit 1
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "Bu betik root/sudo gerektiriyor (paket kurulumu, systemd servisi, firewall icin)." >&2
  echo "Calistirin: sudo $0 $*" >&2
  exit 1
fi

KAYNAK_KLASOR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

adim() { echo ""; echo "== $1 =="; }

# ---------------------------------------------------------------- 1. Paketler
adim "1/5 Sistem paketleri"

if command -v apt-get >/dev/null 2>&1; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip rsync
  if [ "$LOGO_KUR" = 1 ]; then
    apt-get install -y unixodbc unixodbc-dev curl gnupg
  fi
else
  echo "apt-get bulunamadi — bu betik Debian/Ubuntu icin yazildi." >&2
  echo "Elle kurulmasi gerekenler: python3, python3-venv, python3-pip, rsync" >&2
  [ "$LOGO_KUR" = 1 ] && echo "  Logo baglantisi icin ayrica: unixodbc, unixodbc-dev" >&2
fi

# ---------------------------------------------------------------- 2. Kopyala
adim "2/5 Dosyalar $HEDEF_KLASOR konumuna kopyalaniyor"

if [ "$KAYNAK_KLASOR" = "$HEDEF_KLASOR" ]; then
  echo "Kaynak ve hedef ayni, kopyalama atlaniyor."
else
  mkdir -p "$HEDEF_KLASOR"
  # Var olan veritabani ve ayarlar korunur; kod dosyalari uzerine yazilir.
  rsync -a \
    --exclude 'license_reminders.db' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude 'venv' \
    --exclude 'backups' \
    --exclude 'deploy_linux.sh' \
    --exclude 'install.ps1' \
    --exclude 'server.ps1' \
    --exclude 'start_hidden.vbs' \
    "$KAYNAK_KLASOR/" "$HEDEF_KLASOR/"
  echo "Kopyalandi."
fi

if ! id "$SERVIS_KULLANICI" >/dev/null 2>&1; then
  useradd --system --home-dir "$HEDEF_KLASOR" --shell /usr/sbin/nologin "$SERVIS_KULLANICI"
  echo "Servis kullanicisi olusturuldu: $SERVIS_KULLANICI"
fi
mkdir -p "$HEDEF_KLASOR/backups"
chown -R "$SERVIS_KULLANICI:$SERVIS_KULLANICI" "$HEDEF_KLASOR"

# ---------------------------------------------------------------- 3. venv
adim "3/5 Python sanal ortami ve bagimliliklar"

sudo -u "$SERVIS_KULLANICI" python3 -m venv "$HEDEF_KLASOR/venv"
sudo -u "$SERVIS_KULLANICI" "$HEDEF_KLASOR/venv/bin/pip" install --upgrade pip --quiet

if [ "$LOGO_KUR" = 1 ]; then
  sudo -u "$SERVIS_KULLANICI" "$HEDEF_KLASOR/venv/bin/pip" install -r "$HEDEF_KLASOR/requirements.txt"
  echo ""
  echo "NOT: pyodbc kuruldu ama Logo'ya baglanmak icin Microsoft ODBC Driver 18"
  echo "for SQL Server'in da sisteme kurulu olmasi gerekiyor (unixodbc yeterli degil)."
  echo "Kurulum adimlari: https://learn.microsoft.com/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server"
else
  echo "Atlandi (Logo baglantisi gerekmiyorsa gerek yok). Gerekirse: sudo ./deploy_linux.sh --logo"
fi

# ---------------------------------------------------------------- 4. Firewall
adim "4/5 Firewall (port $PORT)"

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow "$PORT"/tcp
  echo "ufw kurali eklendi."
elif command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port="$PORT"/tcp
  firewall-cmd --reload
  echo "firewalld kurali eklendi."
else
  echo "Aktif bir firewall (ufw/firewalld) tespit edilemedi — bulut saglayicisinin"
  echo "guvenlik grubunda/security group'unda $PORT portunun LAN'a acik oldugunu elle kontrol edin."
fi

# ---------------------------------------------------------------- 5. systemd
adim "5/5 systemd servisi"

SERVICE_FILE="/etc/systemd/system/piramit-muhasebe.service"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Piramit Muhasebe - Lisans Takip Uygulamasi
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVIS_KULLANICI
Group=$SERVIS_KULLANICI
WorkingDirectory=$HEDEF_KLASOR
ExecStart=$HEDEF_KLASOR/venv/bin/python $HEDEF_KLASOR/app.py
Restart=on-failure
RestartSec=5
# Uygulama zaten kendi SQLite dosyasina/backups klasorune yaziyor, baska
# hicbir sisteme yazmasina gerek yok.
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$HEDEF_KLASOR

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable piramit-muhasebe
systemctl restart piramit-muhasebe

# ---------------------------------------------------------------- Bitis
adim "Kurulum tamamlandi"

sleep 2
systemctl status piramit-muhasebe --no-pager -l | head -10

echo ""
echo "Tarayicidan http://<sunucu-ip>:$PORT adresine gidip giris yapabilirsiniz."
echo "Loglar icin: sudo journalctl -u piramit-muhasebe -f"
echo "Yeniden baslatmak icin: sudo systemctl restart piramit-muhasebe"
