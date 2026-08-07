"""Ekran modunun ikinci slaydı: tüm yurtların eth1 trafiği.

Televizyonda 34 küçük grafik yan yana. Tek tek okunmaları değil, **bir bakışta
karşılaştırılmaları** amaçlanıyor: hangi yurt yüklü, hangisi sessiz, nerede
sıra dışı bir sıçrama var. Bu yüzden her grafik kendi ölçeğinde çiziliyor ve
tepe değeri yanına yazılıyor — ortak ölçek kullanılsaydı küçük yurtlar düz
çizgi olarak görünürdü.

Veri Zabbix geçmişinden geliyor ve birkaç dakika önbellekte tutuluyor: ekran
her dakika yeniden çiziliyor, 60 item'lık sorguyu her seferinde tekrarlamanın
görsel bir faydası yok.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from .render import esc, fmt_bps
from .zabbix import ZabbixClient

log = logging.getLogger(__name__)

ARAYUZ_DESENI = re.compile(r"Interface\s+([^(]+)\(.*?\):\s*Bits\s+(received|sent)", re.I)

BACAK = "eth1"          # kullanıcı isteği: internet bacağı olarak eth1
PENCERE_SAAT = 3        # televizyonda 3 saat, 6 saatten daha okunaklı bir eğri veriyor
ONBELLEK_SN = 180
NOKTA = 80              # küçük grafikte 360 nokta gereksiz; tepe koruyarak seyreltilir

_onbellek: tuple[float, dict] | None = None


def _seyrelt(noktalar: list[tuple[int, float]], hedef: int = NOKTA) -> list[tuple[int, float]]:
    """Kovalara böler, her kovanın EN BÜYÜĞÜNÜ alır.

    Ortalama alınsaydı kısa süreli sıçramalar silinirdi; oysa duvardaki ekranda
    asıl dikkat çekmesi gereken şey onlar.
    """
    if len(noktalar) <= hedef:
        return noktalar
    boy = len(noktalar) / hedef
    cikti = []
    for i in range(hedef):
        parca = noktalar[int(i * boy):int((i + 1) * boy)] or [noktalar[min(int(i * boy), len(noktalar) - 1)]]
        cikti.append(max(parca, key=lambda p: p[1]))
    return cikti


def veri(config: dict[str, Any], now: int) -> dict[str, dict[str, Any]]:
    """hostid -> {'gelen': [(t,v)], 'giden': [(t,v)]}. Hata durumunda boş sözlük."""
    global _onbellek
    if _onbellek and (now - _onbellek[0]) < ONBELLEK_SN:
        return _onbellek[1]

    try:
        with ZabbixClient(config["zabbix"]) as z:
            hostlar = z.get_hosts(config["zabbix"]["host_groups"])
            items = z.get_items([h["hostid"] for h in hostlar])

            esleme: dict[str, dict[str, str]] = {}
            for it in items:
                anahtar = it.get("key_", "")
                if not (anahtar.startswith("net.if.in[") or anahtar.startswith("net.if.out[")):
                    continue
                m = ARAYUZ_DESENI.search(it.get("name", ""))
                if not m or m.group(1).strip() != BACAK:
                    continue
                yon = "gelen" if m.group(2).lower() == "received" else "giden"
                esleme.setdefault(it["hostid"], {})[yon] = it["itemid"]

            idler = [i for v in esleme.values() for i in v.values()]
            if not idler:
                return {}
            gecmis = z.get_history(idler, now - PENCERE_SAAT * 3600, now, value_type=3)
    except Exception:
        log.exception("Ekran trafik verisi alınamadı — slayt boş gösterilecek.")
        # Eski önbellek varsa onu kullanmak, hiç göstermemekten iyi.
        return _onbellek[1] if _onbellek else {}

    sonuc = {
        hid: {
            "gelen": _seyrelt(gecmis.get(y.get("gelen", ""), [])),
            "giden": _seyrelt(gecmis.get(y.get("giden", ""), [])),
        }
        for hid, y in esleme.items()
    }
    _onbellek = (now, sonuc)
    return sonuc


def _mini_grafik(gelen: list[tuple[int, float]], giden: list[tuple[int, float]],
                 kimlik: str) -> tuple[str, float, float]:
    """Küçük alan grafiği. Dönen: (svg, tepe değeri, son değer)."""
    tum = [d for _, d in gelen] + [d for _, d in giden]
    if not tum:
        return '<div class="yok">veri yok</div>', 0.0, 0.0
    tepe = max(tum) or 1.0
    zamanlar = [t for t, _ in gelen + giden]
    t0, t1 = min(zamanlar), max(zamanlar)
    genislik = (t1 - t0) or 1

    EN, BOY = 300.0, 78.0

    def yol(noktalar, kapat: bool) -> str:
        if not noktalar:
            return ""
        p = " ".join(
            f"{'M' if i == 0 else 'L'}{(t - t0) / genislik * EN:.1f},"
            f"{BOY - (d / tepe) * BOY:.1f}"
            for i, (t, d) in enumerate(noktalar)
        )
        if kapat:
            p += (f" L{(noktalar[-1][0] - t0) / genislik * EN:.1f},{BOY:.1f}"
                  f" L{(noktalar[0][0] - t0) / genislik * EN:.1f},{BOY:.1f} Z")
        return p

    svg = f"""<svg viewBox="0 0 {EN:.0f} {BOY:.0f}" preserveAspectRatio="none" class="mini">
<defs>
  <linearGradient id="d{kimlik}" x1="0" y1="0" x2="0" y2="{BOY:.0f}" gradientUnits="userSpaceOnUse">
    <stop offset="0%" stop-color="#ef4444" stop-opacity=".75"/>
    <stop offset="42%" stop-color="#eab308" stop-opacity=".45"/>
    <stop offset="100%" stop-color="#22c55e" stop-opacity=".10"/>
  </linearGradient>
  <linearGradient id="c{kimlik}" x1="0" y1="{BOY:.0f}" x2="0" y2="0" gradientUnits="userSpaceOnUse">
    <stop offset="0%" stop-color="#22c55e"/><stop offset="42%" stop-color="#eab308"/>
    <stop offset="100%" stop-color="#ef4444"/>
  </linearGradient>
</defs>
<path d="{yol(gelen, True)}" fill="url(#d{kimlik})"/>
<path d="{yol(gelen, False)}" fill="none" stroke="url(#c{kimlik})" stroke-width="2"
      vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
<path d="{yol(giden, False)}" fill="none" stroke="#7e7c74" stroke-width="1.2"
      vector-effect="non-scaling-stroke" stroke-linejoin="round" opacity=".8"/>
</svg>"""
    son = gelen[-1][1] if gelen else 0.0
    return svg, tepe, son


def slayt(config: dict[str, Any], snapshots, durumlar: dict[str, str], now: int) -> str:
    """İkinci slaydın gövdesi."""
    g = veri(config, now)

    kartlar = []
    for sira, s in enumerate(sorted(snapshots, key=lambda x: _kisa(x.name).lower())):
        d = g.get(s.hostid) or {}
        svg, tepe, son = _mini_grafik(d.get("gelen", []), d.get("giden", []), f"t{sira}")
        durum = durumlar.get(s.hostid, "iyi")
        kartlar.append(
            f'<div class="tkart {durum}">'
            f'<div class="tbas"><span class="tad">{esc(_kisa(s.name))}</span>'
            f'<span class="tson">{esc(fmt_bps(son)) if tepe else ""}</span></div>'
            f'<div class="tgrafik">{svg}</div>'
            f'<div class="ttepe">{("tepe " + fmt_bps(tepe)) if tepe else "&nbsp;"}</div>'
            f"</div>"
        )

    olcum_var = sum(1 for v in g.values() if v.get("gelen"))
    return f"""
<header class="ust">
  <div class="baslik">İNTERNET TRAFİĞİ · {esc(BACAK.upper())}</div>
  <div class="tgosterge">
    <span><i class="alan"></i>gelen</span>
    <span><i class="cizgi"></i>giden</span>
    <span class="sonuk">son {PENCERE_SAAT} saat · {olcum_var}/{len(snapshots)} yurtta ölçüm</span>
  </div>
</header>
<div class="tizgara">{"".join(kartlar)}</div>
"""


def _kisa(ad: str) -> str:
    from .reports_html import _kisa_ad

    return _kisa_ad(ad)


CSS = """
/* ---- slayt 2: trafik ---- */
.tgosterge{display:flex;gap:1.4vw;align-items:center;font-size:1vw;color:var(--ink2)}
.tgosterge span{display:inline-flex;align-items:center;gap:.45vw}
.tgosterge i{width:1.2vw;height:.5vw;border-radius:.15vw;display:inline-block}
.tgosterge i.alan{background:linear-gradient(90deg,#22c55e,#eab308,#ef4444)}
.tgosterge i.cizgi{height:.16vw;background:var(--muted)}
.tgosterge .sonuk{color:var(--muted)}

.tizgara{flex:1;min-height:0;display:grid;gap:.45vw;padding:.8vw 1.2vw 1.2vw;
  grid-template-columns:repeat(6,1fr);grid-auto-rows:1fr}
.tkart{background:var(--kart);border:1px solid var(--cizgi);border-radius:.6vw;
  padding:.45vw .6vw .3vw;display:flex;flex-direction:column;min-width:0;overflow:hidden}
.tkart.uyari{border-color:rgba(245,184,61,.5)}
.tkart.kritik{border-color:rgba(240,90,90,.6);background:rgba(240,90,90,.07)}
.tbas{display:flex;justify-content:space-between;align-items:baseline;gap:.4vw}
.tad{font-size:1.02vw;font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tson{font-size:1vw;font-weight:700;color:var(--iyi);font-variant-numeric:tabular-nums;
  white-space:nowrap}
.tkart.uyari .tson{color:var(--uyari)}
.tkart.kritik .tson{color:var(--kritik)}
.tgrafik{flex:1;min-height:0;margin:.25vw 0 .1vw}
.tgrafik .mini{width:100%;height:100%;display:block}
.tgrafik .yok{font-size:.85vw;color:var(--muted);display:flex;align-items:center;
  justify-content:center;height:100%}
.ttepe{font-size:.78vw;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
"""
