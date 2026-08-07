"""Yapılandırma dosyasının okunması ve varsayılan değerlerle birleştirilmesi."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "zabbix": {
        "url": "",
        "token": "",
        "user": "",
        "password": "",
        "host_groups": [],
        "exclude_hosts": [],
        "verify_ssl": True,
        "timeout": 30,
    },
    "poll": {
        "check_interval_minutes": 5,
        "dashboard_refresh_minutes": 10,
        "report_refresh_minutes": 10,
        "history_window_minutes": 15,
    },
    "thresholds": {
        "loss_warn": 2.0,
        "loss_crit": 10.0,
        "latency_warn_ms": 80,
        "latency_crit_ms": 200,
        "cpu_warn": 80,
        "cpu_crit": 92,
        "mem_warn": 85,
        "mem_crit": 95,
        "bandwidth_util_warn": 75,
        "bandwidth_util_crit": 90,
        "flap_count_1h": 4,
        "regional_outage_min_hosts": 3,
        "reboot_recent_minutes": 20,
        "stale_data_minutes": 15,
        # Bir bulgunun arıza sayılması için arka arkaya kaç turda görülmesi gerektiği.
        # Anlık dalgalanmaların arıza kaydı ve mail üretmesini engeller.
        "confirm_cycles": 2,
        # Arayüz hata sayacı iki ölçüm arasında bu kadar artarsa bulgu üretilir.
        "if_error_artis_esigi": 1,
    },
    # mode: off (doluluk hesaplanmaz) | fixed (default_mbps) | learned (geçmişten öğrenir)
    "bandwidth": {
        "mode": "learned",
        "default_mbps": 100,
        "per_host": {},
        "learn_min_days": 7,
        "learn_min_samples": 500,
    },
    "wan": {"interfaces": {}},
    "email": {
        "enabled": True,
        "smtp_host": "",
        "smtp_port": 587,
        "use_tls": True,
        "use_ssl": False,
        "username": "",
        "password": "",
        "sender": "",
        "recipients": [],
        # Arıza kaydı açıldıktan sonra mail atmadan önce beklenecek süre:
        # sorunun kalıcı olduğunu görmeden bildirim gitmesin.
        "min_duration_minutes": 5,
        "alert_cooldown_minutes": 60,
        "send_recovery": True,
        "min_severity": "warning",
    },
    "report": {
        "weekly_enabled": True,
        "weekly_day": "monday",
        # Kendiliğinden düzelen ve bundan kısa süren olaylar yönetici raporunda
        # tek tek gösterilmez; sadece toplu bir satırda özetlenir.
        "onemli_sure_dakika": 10,
        # Kısa da olsa bu kadar tekrarlayan sorun "kalıcı" sayılır ve öne çıkar.
        "tekrar_esigi": 4,
        "weekly_hour": 9,
        "recipients": [],
        # Aylık yönetici raporu: PDF eki olarak gider.
        # Ayın kaçında gönderileceği monthly_day ile belirlenir; 1 = ayın ilk
        # günü, yani biten ayın özeti.
        "monthly_enabled": True,
        "monthly_day": 1,
        "monthly_hour": 9,
        "monthly_recipients": [],
    },
    "dashboard": {
        "enabled": True,
        "bind": "0.0.0.0",
        "port": 8787,
        "output_file": "dashboard.html",
        # E-postalara konacak adres. bind değeri buraya yazılamaz:
        # 127.0.0.1 "bu makine" demektir, mailin açıldığı cihazda karşılığı yoktur.
        "public_url": "",
        "auth": {"enabled": True, "username": "yurtnet", "password": "", "session_days": 0},
    },
    # retain_days: ham ölçümler (hacimli, kısa vadede gerekli)
    # retain_incident_days: arıza kayıtları (küçük, uzun vadeli trend için değerli)
    "storage": {"db_file": "yurtnet.db", "retain_days": 90, "retain_incident_days": 730},
    "item_keys": {
        "ping": ["icmpping"],
        "loss": ["icmppingloss"],
        "latency": ["icmppingsec"],
        "cpu": ["system.cpu.util"],
        "mem": ["vm.memory.util"],
        "uptime": ["system.net.uptime", "system.hw.uptime", "system.uptime"],
        "if_in": ["net.if.in["],
        "if_out": ["net.if.out["],
        "if_speed": ["net.if.speed"],
        "if_status": ["net.if.status"],
        "if_errors": [
            "net.if.in.errors",
            "net.if.out.errors",
            "net.if.in.discards",
            "net.if.out.discards",
        ],
    },
    "regions": {
        "tag": "bolge",
        "host_group_prefix": "Bolge/",
        "from_host_name": True,
        "default": "Bilinmiyor",
    },
}

# config.yaml yerine ortam değişkeni ile geçilebilecek gizli alanlar.
ENV_OVERRIDES = {
    "YURTNET_ZABBIX_TOKEN": ("zabbix", "token"),
    "YURTNET_ZABBIX_USER": ("zabbix", "user"),
    "YURTNET_ZABBIX_PASSWORD": ("zabbix", "password"),
    "YURTNET_SMTP_USERNAME": ("email", "username"),
    "YURTNET_SMTP_PASSWORD": ("email", "password"),
}

# İç içe alanlar için ayrı tablo: ENV -> (bölüm, alt bölüm, alan)
NESTED_ENV_OVERRIDES = {
    "YURTNET_DASHBOARD_PASSWORD": ("dashboard", "auth", "password"),
}


class ConfigError(Exception):
    pass


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(path: str | os.PathLike[str] = "config.yaml") -> dict[str, Any]:
    """config.yaml'ı oku, varsayılanlarla birleştir, doğrula."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(
            f"{config_path} bulunamadı. config.example.yaml dosyasını config.yaml olarak "
            "kopyalayıp kendi bilgilerinizi girin."
        )

    with config_path.open("r", encoding="utf-8") as fh:
        user_config = yaml.safe_load(fh) or {}

    config = _merge(DEFAULTS, user_config)

    for env_name, (section, key) in ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value:
            config[section][key] = value

    for env_name, (section, sub, key) in NESTED_ENV_OVERRIDES.items():
        value = os.environ.get(env_name)
        if value:
            config[section][sub][key] = value

    # Göreli dosya yolları config.yaml'ın bulunduğu dizine göre çözülür.
    base_dir = config_path.resolve().parent
    config["_base_dir"] = base_dir
    config["storage"]["db_file"] = str(base_dir / config["storage"]["db_file"])
    config["dashboard"]["output_file"] = str(base_dir / config["dashboard"]["output_file"])

    # Panodan girilen mail ayarları config.yaml'ın üzerine biner. En sonda
    # uygulanır ki doğrulama gerçekten kullanılacak değerleri görsün.
    from . import ayarlar

    ayarlar.uygula(config)

    _validate(config)
    return config


def _validate(config: dict[str, Any]) -> None:
    zbx = config["zabbix"]
    if not zbx["url"]:
        raise ConfigError("zabbix.url boş olamaz.")
    if not zbx["token"] and not (zbx["user"] and zbx["password"]):
        raise ConfigError(
            "Zabbix kimlik bilgisi yok: ya zabbix.token ya da zabbix.user + zabbix.password girin."
        )

    mail = config["email"]
    if mail["enabled"]:
        # Eksik mail ayarı uygulamayı durdurmaz, yalnızca gönderimi kapatır.
        # Ayarlar panonun içindeki sayfadan giriliyor; hata fırlatılsaydı
        # uygulama açılmaz, dolayısıyla ayarı düzeltecek sayfaya da
        # ulaşılamazdı. İzleme mailden bağımsız çalışmaya devam etmeli.
        eksik = [f for f in ("smtp_host", "sender") if not mail[f]]
        if not mail["recipients"]:
            eksik.append("recipients")
        if eksik:
            mail["enabled"] = False
            log.warning(
                "Mail gönderimi kapatıldı, şu alanlar boş: %s. "
                "Panodaki Ayarlar sayfasından doldurabilirsiniz.",
                ", ".join(eksik),
            )
        if mail["use_tls"] and mail["use_ssl"]:
            raise ConfigError("email.use_tls ve email.use_ssl aynı anda açık olamaz.")
        if mail["min_severity"] not in ("info", "warning", "critical"):
            raise ConfigError("email.min_severity: info, warning veya critical olmalı.")

    dash = config["dashboard"]
    if dash.get("enabled"):
        auth = dash.get("auth") or {}
        exposed = dash["bind"] not in ("127.0.0.1", "localhost", "::1")
        if exposed and auth.get("enabled") and not auth.get("password"):
            raise ConfigError(
                "Dashboard ağa açık (dashboard.bind: "
                f"{dash['bind']}) ama parola tanımlı değil. "
                "dashboard.auth.password alanını doldurun ya da "
                "YURTNET_DASHBOARD_PASSWORD ortam değişkenini tanımlayın."
            )
        if exposed and not auth.get("enabled"):
            raise ConfigError(
                "Dashboard ağa açıkken dashboard.auth.enabled kapatılamaz — "
                "tabloda yurtların IP adresleri görünüyor. Sadece bu makineden "
                "erişim için dashboard.bind: 127.0.0.1 yapın."
            )

    if config["report"]["weekly_day"].lower() not in (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ):
        raise ConfigError("report.weekly_day geçersiz (monday..sunday).")

    # 29-31 kabul edilmez: her ay o gün olmadığı için rapor bazı aylar hiç
    # gitmez. 28 en geç güvenli gün.
    if not 1 <= int(config["report"].get("monthly_day", 1)) <= 28:
        raise ConfigError("report.monthly_day 1 ile 28 arasında olmalı.")
