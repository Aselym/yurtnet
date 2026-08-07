"""Panodan girilen mail ayarlarının saklanması.

Neden config.yaml'a yazılmıyor: o dosya elle yazılmış, yorum satırlarıyla dolu
bir belge. `yaml.dump` ile geri yazıldığında bütün yorumlar ve sıralama
kaybolur. Bunun yerine ayrı bir örtü dosyası tutulur; config.yaml el değmemiş
kalır, panodan girilen değerler onun üzerine biner.

Öncelik: panodan girilen değer > ortam değişkeni > config.yaml.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DOSYA_ADI = "mail_ayarlari.json"

# Panodan düzenlenebilen alanlar. Buraya yazılmayan hiçbir şey dosyadan
# okunmaz; bozuk ya da elle kurcalanmış bir dosya beklenmedik ayar enjekte
# edemesin.
EMAIL_ALANLARI = (
    "enabled", "smtp_host", "smtp_port", "use_ssl", "use_tls",
    "username", "password", "sender", "recipients",
    "min_severity", "min_duration_minutes", "alert_cooldown_minutes", "send_recovery",
)
RAPOR_ALANLARI = (
    "monthly_enabled", "monthly_day", "monthly_hour", "monthly_recipients",
    "weekly_enabled", "recipients",
)


def _yol(config: dict[str, Any]) -> Path:
    return Path(config.get("_base_dir") or ".") / DOSYA_ADI


def yukle(config: dict[str, Any]) -> dict[str, Any]:
    """Kayıtlı ayarları okur. Dosya yoksa ya da bozuksa boş sözlük döner."""
    yol = _yol(config)
    if not yol.exists():
        return {}
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        log.exception("%s okunamadı, yok sayılıyor.", yol.name)
        return {}
    return veri if isinstance(veri, dict) else {}


def kaydet(config: dict[str, Any], email: dict[str, Any], rapor: dict[str, Any]) -> None:
    """Ayarları diske yazar ve dosya iznini kısar (parola içeriyor)."""
    yol = _yol(config)
    veri = {
        "email": {k: v for k, v in email.items() if k in EMAIL_ALANLARI},
        "report": {k: v for k, v in rapor.items() if k in RAPOR_ALANLARI},
    }
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, yol)  # yarım yazılmış dosya bırakmamak için
    try:
        yol.chmod(0o600)  # Windows'ta etkisiz, Linux'ta önemli
    except OSError:
        pass
    log.info("Mail ayarları kaydedildi: %s", yol.name)


def uygula(config: dict[str, Any]) -> None:
    """Kayıtlı ayarları çalışan yapılandırmanın üzerine bindirir.

    Yerinde değiştirir: çalışan süreçteki sözlüğün aynısı olduğu için kayıttan
    hemen sonra çağrıldığında yeniden başlatmaya gerek kalmaz.
    """
    veri = yukle(config)
    if not veri:
        return
    for bolum, alanlar in (("email", EMAIL_ALANLARI), ("report", RAPOR_ALANLARI)):
        for anahtar, deger in (veri.get(bolum) or {}).items():
            if anahtar in alanlar:
                config[bolum][anahtar] = deger


def eksikler(config: dict[str, Any]) -> list[str]:
    """Mail açık ama gönderim için eksik olan alanlar."""
    mail = config["email"]
    if not mail.get("enabled"):
        return []
    eksik = []
    if not mail.get("smtp_host"):
        eksik.append("sunucu adresi")
    if not mail.get("sender"):
        eksik.append("gönderen adresi")
    if not mail.get("recipients"):
        eksik.append("teknik servis alıcıları")
    return eksik
