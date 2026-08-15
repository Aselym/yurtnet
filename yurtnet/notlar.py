"""Yurt İnternet Durumu tablosundaki "Not" sütunu — serbest metin, panodan girilir.

Ayrı bir JSON dosyası: config.yaml, veritabanı ve arıza kayıtlarından bağımsız
küçük bir not defteri. Servis ekibi "buraya gitmeden önce X'i sor" gibi kalıcı
olmayan, kurala bağlanmayan hatırlatmaları buraya yazar — arıza kaydı, tekrar
listesi, analiz gibi otomatik üretilen hiçbir şeyle karışmaz.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DOSYA_ADI = "notlar.json"
UZUNLUK_SINIRI = 300


def _yol(config: dict[str, Any]) -> Path:
    return Path(config.get("_base_dir") or ".") / DOSYA_ADI


def yukle(config: dict[str, Any]) -> dict[str, str]:
    yol = _yol(config)
    if not yol.exists():
        return {}
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        log.exception("%s okunamadı, yok sayılıyor.", yol.name)
        return {}
    return veri if isinstance(veri, dict) else {}


def al(config: dict[str, Any], hostid: str) -> str:
    return yukle(config).get(hostid, "")


def kaydet(config: dict[str, Any], hostid: str, metin: str) -> None:
    """Notu yazar; boş metin gelirse notu tamamen kaldırır."""
    veri = yukle(config)
    metin = metin.strip()[:UZUNLUK_SINIRI]
    if metin:
        veri[hostid] = metin
    else:
        veri.pop(hostid, None)

    yol = _yol(config)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, yol)
