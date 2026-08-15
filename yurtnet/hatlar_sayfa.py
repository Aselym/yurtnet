"""Hat Ayarları sayfası: yurt başına internet hattı (port) adı, hızı, cihaz sayısı.

Zabbix'ten hangi arayüzlerin var olduğu okunur (isim yazılamaz, keşfedilir);
isim ve hız servis ekibi tarafından elle girilir. Girilen hız yalnızca ekranda
görünen bir etiket değil — hat_ayarlari.py üzerinden tüm doluluk
değerlendirmelerine (SATURATION bulgusu, analiz, PDF, ekran modu) girer.

Yeni bir yurt Zabbix'teki host grubuna eklendiği an, bir sonraki kontrol
turunda kendiliğinden izlenmeye başlar (bkz. collect.collect — host listesi
her turda Zabbix'ten taze çekiliyor). Bu sayfa da aynı şekilde: yenilendiğinde
yeni yurdu otomatik listeler, ekstra bir kurulum adımı gerekmez.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import hat_ayarlari, pages
from .render import esc
from .reports_html import _kisa_ad
from .trafik import ARAYUZ_DESENI

log = logging.getLogger(__name__)

_onbellek: tuple[float, list[dict]] | None = None
ONBELLEK_SN = 90


def _yurt_arayuzleri(config: dict[str, Any], now: int) -> list[dict[str, Any]]:
    """Zabbix'ten her yurdun WAN adayı arayüzlerini çeker.

    Sonuç önbelleklenir: bu sayfa arka arkaya birkaç kez kaydedilirse (birden
    çok yurt üst üste düzenlenirse) her seferinde tüm host'ları yeniden
    sorgulamak gereksiz.
    """
    global _onbellek
    if _onbellek and (now - _onbellek[0]) < ONBELLEK_SN:
        return _onbellek[1]

    from .zabbix import ZabbixClient, ZabbixError

    try:
        with ZabbixClient(config["zabbix"]) as z:
            hostlar = sorted(
                z.get_hosts(config["zabbix"]["host_groups"]), key=lambda h: h["name"]
            )
            items = z.get_items([h["hostid"] for h in hostlar])
    except ZabbixError:
        log.exception("Hat Ayarları için Zabbix'e ulaşılamadı")
        return _onbellek[1] if _onbellek else []

    items_by_host: dict[str, list[dict]] = {}
    for it in items:
        items_by_host.setdefault(it["hostid"], []).append(it)

    sonuc = []
    for h in hostlar:
        arayuzler: set[str] = set()
        for it in items_by_host.get(h["hostid"], []):
            m = ARAYUZ_DESENI.search(it.get("name", ""))
            if m:
                arayuzler.add(m.group(1).strip())
        sonuc.append({
            "hostid": h["hostid"], "host": h["host"], "ad": _kisa_ad(h["name"]),
            "arayuzler": sorted(arayuzler),
        })
    _onbellek = (now, sonuc)
    return sonuc


CSS = """
.hat-yurt{margin-bottom:14px}
.hat-yurt summary{cursor:pointer;padding:13px 16px;font-size:14px;font-weight:650;
  display:flex;align-items:center;gap:10px;list-style:none}
.hat-yurt summary::-webkit-details-marker{display:none}
.hat-yurt summary::before{content:'▸';color:var(--muted);font-size:11px;width:10px}
.hat-yurt[open] summary::before{content:'▾'}
.hat-yurt summary .bolge{color:var(--muted);font-weight:500;font-size:12.5px}
.hat-yurt summary .ozet{margin-left:auto;font-size:12px;color:var(--muted);font-weight:500}
.hat-govde{padding:0 16px 16px}
.hat-basliklar{display:grid;grid-template-columns:26px 90px 1fr 130px;gap:10px;
  margin-bottom:6px}
.hat-basliklar span{font-size:10.5px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em}
.hat-satir{display:grid;grid-template-columns:26px 90px 1fr 130px;gap:10px;align-items:center;
  margin-bottom:9px}
.hat-satir input[type=text],.hat-satir input[type=number]{background:var(--plane);color:var(--ink);
  border:1px solid var(--line);border-radius:7px;padding:8px 10px;font-size:13px;
  font-family:inherit;min-width:0}
.hat-birincil{display:flex;align-items:center;justify-content:center}
.hat-birincil input{width:16px;height:16px;cursor:pointer}
.hat-arayuz{font-size:13px;font-family:ui-monospace,monospace;color:var(--ink2);
  background:var(--kart2,var(--plane));border-radius:7px;padding:8px 10px;text-align:center}
.hat-cihaz{display:flex;align-items:center;gap:10px;margin:14px 0 4px;padding-top:12px;
  border-top:1px solid var(--line)}
.hat-cihaz label{font-size:13px;color:var(--ink2);white-space:nowrap}
.hat-cihaz input{width:90px;background:var(--plane);color:var(--ink);border:1px solid var(--line);
  border-radius:7px;padding:7px 10px;font-size:13px;font-family:inherit}
.hat-kaydet{margin-top:12px;font-family:inherit;font-size:13px;font-weight:600;
  padding:8px 16px;border-radius:7px;border:1px solid var(--seri);background:var(--seri);
  color:#fff;cursor:pointer}
.hat-kaydet:hover{filter:brightness(1.08)}
.hat-yok{padding:0 16px 16px;font-size:13px;color:var(--muted)}
"""


def _yurt_karti(y: dict[str, Any], mevcut: dict[str, Any]) -> str:
    hatlar = (mevcut.get("hatlar")) or {}
    cihaz = mevcut.get("cihaz_sayisi") or ""
    birincil = mevcut.get("birincil_arayuz") or ""

    if not y["arayuzler"]:
        return (
            f'<details class="hat-yurt"><summary>{esc(y["ad"])} '
            f'<span class="bolge">{esc(y["host"])}</span></summary>'
            f'<div class="hat-yok">Bu yurtta Zabbix üzerinden arayüz bulunamadı '
            f'(SNMP keşfi eksik olabilir).</div></details>'
        )

    tanimli = sum(1 for a in y["arayuzler"] if hatlar.get(a, {}).get("hiz_mbps"))
    ozet = f"{tanimli}/{len(y['arayuzler'])} hat tanımlı" + (
        f" · {cihaz} cihaz" if cihaz else ""
    ) + (f" · birincil {birincil}" if birincil else "")

    satirlar = []
    for arayuz in y["arayuzler"]:
        bilgi = hatlar.get(arayuz) or {}
        secili = " checked" if arayuz == birincil else ""
        satirlar.append(
            f'<div class="hat-satir">'
            f'<div class="hat-birincil">'
            f'<input type="radio" name="birincil" value="{esc(arayuz)}"{secili} '
            f'title="Bu hat, yurdun asıl interneti — otomatik seçime bırakma"></div>'
            f'<div class="hat-arayuz">{esc(arayuz)}</div>'
            f'<input type="text" name="isim__{esc(arayuz)}" placeholder="Hat adı (ör. Türk Telekom Fiber)" '
            f'value="{esc(bilgi.get("isim") or "")}" maxlength="60">'
            f'<input type="number" name="hiz__{esc(arayuz)}" placeholder="Mbps" min="0" step="1" '
            f'value="{esc(str(bilgi.get("hiz_mbps") or ""))}">'
            f"</div>"
        )

    return f"""<details class="hat-yurt"><summary>{esc(y["ad"])}
  <span class="bolge">{esc(y["host"])}</span><span class="ozet">{esc(ozet)}</span></summary>
<div class="hat-govde">
<form method="POST" action="/hatlar">
  <input type="hidden" name="host" value="{esc(y["host"])}">
  <input type="hidden" name="arayuzler" value="{esc(",".join(y["arayuzler"]))}">
  <div class="hat-basliklar"><span>Birincil</span><span>Port</span><span>Hat adı</span><span>Hız</span></div>
  <div class="hat-satir">
    <div class="hat-birincil"><input type="radio" name="birincil" value=""
      {"checked" if not birincil else ""} title="Otomatik seç (trafiğe göre)"></div>
    <div class="hat-arayuz" style="font-style:italic;color:var(--muted)">otomatik</div>
    <div class="sonuk" style="font-size:12px;grid-column:span 2;align-self:center">
      Hangi hattın "birincil" olduğunu işaretlemezseniz sistem trafiğe bakarak kendisi seçer
      — yedek hatta geçildiğinde bu otomatik değişebilir.</div>
  </div>
  {"".join(satirlar)}
  <div class="hat-cihaz">
    <label for="cihaz_{esc(y["hostid"])}">Yurttaki cihaz sayısı</label>
    <input id="cihaz_{esc(y["hostid"])}" type="number" name="cihaz_sayisi" min="0" step="1"
           value="{esc(str(cihaz))}">
  </div>
  <button class="hat-kaydet" type="submit">Kaydet</button>
</form>
</div></details>"""


def sayfa(config: dict[str, Any], logo: str, mesaj: tuple[str, str] | None = None) -> str:
    now = int(time.time())
    yurtlar = _yurt_arayuzleri(config, now)
    tum_ayarlar = hat_ayarlari.yukle(config)

    bildirim = ""
    if mesaj:
        durum, metin = mesaj
        bildirim = f'<div class="bildirim {esc(durum)}">{esc(metin)}</div>'

    if not yurtlar:
        govde = (
            "<h1>Hat Ayarları</h1>"
            '<p class="alt">Yurt listesi Zabbix\'ten alınamadı.</p>'
        )
    else:
        kartlar = "".join(_yurt_karti(y, tum_ayarlar.get(y["host"], {})) for y in yurtlar)
        govde = (
            "<h1>Hat Ayarları</h1>"
            f'<p class="alt">{len(yurtlar)} yurt · her yurdun internet hattına (portuna) '
            "ad ve hız verin, cihaz sayısını girin. Girilen hız, bu yurttaki tüm hat "
            "doluluğu değerlendirmelerinde (arıza tespiti, analiz, raporlar) kullanılır.</p>"
            + bildirim
            + pages.kart(
                "Yurtlar",
                kartlar,
                aciklama=(
                    "Bir yurdun adına tıklayınca hatları açılır. Hangi arayüzün "
                    "internet hattı olduğunu bilmiyorsanız Trafik Grafikleri "
                    "sayfasından hangisinde trafik aktığına bakabilirsiniz."
                ),
            )
        )

    return pages.shell(
        baslik="Hat Ayarları — Yurt İnterneti",
        aktif="/hatlar",
        govde=govde,
        logo=logo,
        ek_css=CSS + """
.bildirim{border-radius:9px;padding:12px 15px;margin-bottom:18px;font-size:13.5px}
.bildirim.iyi{background:rgba(12,163,12,.11);border:1px solid rgba(12,163,12,.35);color:var(--iyi-ink)}
.bildirim.kotu{background:rgba(208,59,59,.10);border:1px solid rgba(208,59,59,.35);color:var(--kritik-ink)}
""",
    )


def formdan_kaydet(config: dict[str, Any], alanlar: dict[str, list[str]]) -> tuple[str, str]:
    """POST /hatlar gövdesini işler. Dönen: (durum, mesaj)."""
    host = (alanlar.get("host") or [""])[0].strip()
    if not host:
        return "kotu", "Yurt belirtilmedi."

    arayuzler = [a for a in (alanlar.get("arayuzler") or [""])[0].split(",") if a]
    hatlar: dict[str, dict[str, Any]] = {}
    for arayuz in arayuzler:
        isim = (alanlar.get(f"isim__{arayuz}") or [""])[0].strip()[:60]
        ham_hiz = (alanlar.get(f"hiz__{arayuz}") or [""])[0].strip()
        try:
            hiz_mbps = float(ham_hiz) if ham_hiz else 0.0
        except ValueError:
            return "kotu", f"'{arayuz}' için geçersiz hız değeri."
        if hiz_mbps < 0:
            return "kotu", "Hız negatif olamaz."
        if isim or hiz_mbps:
            hatlar[arayuz] = {"isim": isim, "hiz_mbps": hiz_mbps}

    ham_cihaz = (alanlar.get("cihaz_sayisi") or [""])[0].strip()
    try:
        cihaz = int(ham_cihaz) if ham_cihaz else 0
    except ValueError:
        return "kotu", "Cihaz sayısı bir tam sayı olmalı."
    if cihaz < 0:
        return "kotu", "Cihaz sayısı negatif olamaz."

    birincil = (alanlar.get("birincil") or [""])[0].strip()
    if birincil and birincil not in arayuzler:
        return "kotu", "Geçersiz birincil hat seçimi."

    hat_ayarlari.kaydet(config, host, hatlar, cihaz or None, birincil or None)
    return "iyi", f"{host} için ayarlar kaydedildi."
