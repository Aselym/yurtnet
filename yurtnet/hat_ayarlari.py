"""Yurt başına internet hattı (port) adı, hızı ve cihaz sayısı — panodan girilir.

Neden config.yaml'da değil: bunlar sık değişen, çok sayıda küçük değer
(34 yurt × birkaç arayüz). Panodan tek tıkla düzenlenebilir olması,
her seferinde SSH açıp YAML düzenlemekten daha önemli. `ayarlar.py`
(mail ayarları) ile aynı desen: ayrı bir JSON dosyası, config.yaml'a
elle dokunmadan okunur ve yazılır.

Buradaki hız değeri, yalnızca ekranda görünen bir etiket değildir — hat
doluluğu (SATURATION bulgusu, analiz bölümü, PDF, ekran modu, ne varsa)
bu değeri config.yaml'daki bandwidth.per_host'tan bile önce kullanır.
Servis ekibi gerçek abonelik hızını öğrendiği an, TÜM değerlendirmeler
o hıza göre kesinleşir.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DOSYA_ADI = "hat_ayarlari.json"


def _yol(config: dict[str, Any]) -> Path:
    return Path(config.get("_base_dir") or ".") / DOSYA_ADI


def yukle(config: dict[str, Any]) -> dict[str, Any]:
    """{host: {"cihaz_sayisi": int, "hatlar": {arayuz: {"isim":..., "hiz_mbps":...}}}}"""
    yol = _yol(config)
    if not yol.exists():
        return {}
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except Exception:
        log.exception("%s okunamadı, yok sayılıyor.", yol.name)
        return {}
    return veri if isinstance(veri, dict) else {}


def _yaz(config: dict[str, Any], veri: dict[str, Any]) -> None:
    yol = _yol(config)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(gecici, yol)  # yarım yazılmış dosya bırakmamak için


def hat_bilgisi(config: dict[str, Any], host: str, arayuz: str) -> dict[str, Any] | None:
    return ((yukle(config).get(host) or {}).get("hatlar") or {}).get(arayuz)


def hiz(config: dict[str, Any], host: str, arayuz: str) -> float | None:
    """Bu (yurt, arayüz) için elle girilmiş hız. Yoksa None."""
    bilgi = hat_bilgisi(config, host, arayuz)
    if not bilgi:
        return None
    try:
        deger = float(bilgi.get("hiz_mbps") or 0)
    except (TypeError, ValueError):
        return None
    return deger if deger > 0 else None


def birincil_arayuz(config: dict[str, Any], host: str) -> str | None:
    """Servis ekibinin 'asıl internet hattı budur' dediği arayüz.

    Otomatik WAN seçimi trafiğe göre turdan tura değişebilir (ör. yedek hatta
    geçiş). Bir arayüz burada işaretliyse artık heuristiğe bırakılmaz — girilen
    hat adı/hızının hangi arayüze ait olduğu da böylece belirsiz kalmaz.
    """
    deger = (yukle(config).get(host) or {}).get("birincil_arayuz")
    return deger or None


def cihaz_sayisi(config: dict[str, Any], host: str) -> int | None:
    kayit = yukle(config).get(host) or {}
    try:
        deger = int(kayit.get("cihaz_sayisi") or 0)
    except (TypeError, ValueError):
        return None
    return deger if deger > 0 else None


def kaydet(
    config: dict[str, Any], host: str, hatlar: dict[str, dict[str, Any]],
    cihaz_sayisi_degeri: int | None, birincil: str | None = None,
) -> None:
    """Bir yurdun tüm hat bilgilerini, cihaz sayısını ve birincil hattını yazar."""
    veri = yukle(config)
    kayit = veri.setdefault(host, {})
    # Boş isim VE boş hız girilen satırlar saklanmaz — kullanıcı formu temizce
    # boş bırakabilir, sonraki açılışta gereksiz boş satır görmesin.
    temiz_hatlar = {
        arayuz: h for arayuz, h in hatlar.items()
        if (h.get("isim") or "").strip() or (h.get("hiz_mbps") or 0)
    }
    if temiz_hatlar:
        kayit["hatlar"] = temiz_hatlar
    else:
        kayit.pop("hatlar", None)
    if cihaz_sayisi_degeri:
        kayit["cihaz_sayisi"] = cihaz_sayisi_degeri
    else:
        kayit.pop("cihaz_sayisi", None)
    if birincil:
        kayit["birincil_arayuz"] = birincil
    else:
        kayit.pop("birincil_arayuz", None)
    if not kayit:
        veri.pop(host, None)
    else:
        veri[host] = kayit
    _yaz(config, veri)
    log.info("Hat ayarları kaydedildi: %s (%d hat, birincil=%s)", host, len(temiz_hatlar), birincil)
