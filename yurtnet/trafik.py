"""Yurt bazlı arayüz trafiği grafikleri.

Grafana'daki "ANKARA ETH1 / ETH3" panellerinin yurtnet içindeki karşılığı.
Grafana'nın panel JSON'u doğrudan kullanılamaz — o Grafana'nın kendi çizim
motoruna verdiği tanım. Burada aynı veri Zabbix API'sinden çekilip düz SVG
olarak çiziliyor: harici kütüphane yok, kapalı ağda da açılır.

Veri neden yerel veritabanından değil: yurtnet yalnız WAN bacağının toplamını
saklıyor (in_bps/out_bps). Grafana örneğindeki gibi arayüz arayüz (eth1, eth3)
bakabilmek için Zabbix geçmişi gerekiyor.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from . import pages
from .render import esc, fmt_bps
from .zabbix import ZabbixClient, ZabbixError

log = logging.getLogger(__name__)

# "Interface eth1(): Bits received" -> ("eth1", "in")
ARAYUZ_DESENI = re.compile(r"Interface\s+([^(]+)\(.*?\):\s*Bits\s+(received|sent)", re.I)

TRAFIK_CSS = """
.grafikler{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(420px,1fr))}
.tsec{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:18px}
.tsec select{background:var(--plane);color:var(--ink);border:1px solid var(--line);
  border-radius:8px;padding:8px 11px;font-size:13.5px;font-family:inherit}
.tsec .bilgi{font-size:12.5px;color:var(--muted)}
.gosterge{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:12.5px}
.gosterge span{display:inline-flex;align-items:center;gap:7px;color:var(--ink2)}
.gosterge i{width:16px;height:3px;border-radius:2px;display:inline-block}
.ozet{display:flex;gap:20px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:var(--muted)}
.ozet b{color:var(--ink);font-variant-numeric:tabular-nums}
"""


def _arayuzleri_ayikla(items: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """net.if item'larından arayüz -> {'in': itemid, 'out': itemid} çıkarır."""
    bulunan: dict[str, dict[str, str]] = {}
    for it in items:
        anahtar = it.get("key_", "")
        if not (anahtar.startswith("net.if.in[") or anahtar.startswith("net.if.out[")):
            continue
        m = ARAYUZ_DESENI.search(it.get("name", ""))
        if not m:
            continue
        ad = m.group(1).strip()
        yon = "in" if m.group(2).lower() == "received" else "out"
        bulunan.setdefault(ad, {})[yon] = it["itemid"]
    # Yalnız iki yönü de olan arayüzler; tek yönlü grafik yanıltıcı olur.
    return {a: v for a, v in sorted(bulunan.items()) if "in" in v and "out" in v}


def _guzel_tavan(deger: float, bolum: int = 4) -> float:
    """Ekseni yuvarlak bir değere çıkarır.

    Ham tepe kullanılınca eksen "66 / 50 / 33 / 17" gibi okunmayan sayılar
    üretiyordu; 1-2-5 katlarına yuvarlayınca "80 / 60 / 40 / 20" oluyor.
    """
    if deger <= 0:
        return 1.0
    import math

    kuvvet = 10 ** math.floor(math.log10(deger / bolum))
    for kat in (1, 2, 2.5, 5, 10):
        adim = kat * kuvvet
        if adim * bolum >= deger:
            return adim * bolum
    return deger


def _sayi(d: float) -> str:
    """Eksen etiketi: tam sayıysa ondalık gösterme (2.5 kalsın, 20.0 olmasın)."""
    return f"{d:.0f}" if abs(d - round(d)) < 0.05 else f"{d:.1f}"


def _eksen_birimi(tepe: float) -> tuple[float, str]:
    """Y ekseni için ölçek ve birim: 1.2 Gb/s yerine 1200 Mb/s yazmasın."""
    if tepe >= 1e9:
        return 1e9, "Gb/s"
    if tepe >= 1e6:
        return 1e6, "Mb/s"
    if tepe >= 1e3:
        return 1e3, "kb/s"
    return 1.0, "b/s"


def cizgi_grafik(seriler: list[tuple[str, list[tuple[int, float]]]], kimlik: str) -> str:
    """Zaman serisi alan grafiği.

    Renk değere göre yeşilden kırmızıya geçiyor (Grafana'daki GrYlRd şeması):
    yükseklik arttıkça çizgi kızarıyor, böylece tepe noktaları göze çarpıyor.
    """
    dolu = [(ad, n) for ad, n in seriler if n]
    if not dolu:
        return '<p class="bos">Bu aralıkta ölçüm yok.</p>'

    EN, BOY = 560.0, 200.0
    SOL, SAG, UST, ALT = 62.0, 12.0, 14.0, 30.0
    cw, ch = EN - SOL - SAG, BOY - UST - ALT

    tum = [d for _, n in dolu for _, d in n]
    tepe = _guzel_tavan(max(tum) or 1.0)
    zamanlar = [t for _, n in dolu for t, _ in n]
    t0, t1 = min(zamanlar), max(zamanlar)
    genislik = (t1 - t0) or 1

    olcek, birim = _eksen_birimi(tepe)

    def x(t: int) -> float:
        return SOL + (t - t0) / genislik * cw

    def y(d: float) -> float:
        return UST + ch - (d / tepe) * ch

    # Y ekseni: 4 aralık
    izgara, etiketler = [], []
    for i in range(5):
        deger = tepe * i / 4
        yy = y(deger)
        izgara.append(
            f'<line x1="{SOL:.1f}" y1="{yy:.1f}" x2="{SOL + cw:.1f}" y2="{yy:.1f}" '
            f'stroke="var(--grid)" stroke-width="1"/>'
        )
        etiketler.append(
            f'<text x="{SOL - 8:.1f}" y="{yy + 3.5:.1f}" text-anchor="end" font-size="10.5" '
            f'fill="var(--muted)">{_sayi(deger / olcek)} {esc(birim)}</text>'
        )

    # X ekseni: saat etiketleri
    for i in range(5):
        t = t0 + genislik * i / 4
        xx = x(int(t))
        etiketler.append(
            f'<text x="{xx:.1f}" y="{BOY - 10:.1f}" text-anchor="middle" font-size="10.5" '
            f'fill="var(--muted)">{time.strftime("%H:%M", time.localtime(t))}</text>'
        )

    yollar = []
    for sira, (ad, noktalar) in enumerate(dolu):
        p = " ".join(f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(d):.1f}"
                     for i, (t, d) in enumerate(noktalar))
        # Dolgu: çizginin altını tabana kapatır.
        kapali = (
            f"{p} L{x(noktalar[-1][0]):.1f},{UST + ch:.1f} "
            f"L{x(noktalar[0][0]):.1f},{UST + ch:.1f} Z"
        )
        yollar.append(
            f'<path d="{kapali}" fill="url(#dolgu{kimlik})" opacity="{0.5 if sira == 0 else 0.28}"/>'
            f'<path d="{p}" fill="none" stroke="url(#cizgi{kimlik})" stroke-width="{2 if sira == 0 else 1.5}" '
            f'stroke-linejoin="round" stroke-dasharray="{"" if sira == 0 else "4 3"}"/>'
        )

    return f"""<div class="grafik"><svg viewBox="0 0 {EN:.0f} {BOY:.0f}" width="100%"
  role="img" aria-label="Trafik grafiği">
<defs>
  <linearGradient id="cizgi{kimlik}" x1="0" y1="{UST + ch:.0f}" x2="0" y2="{UST:.0f}"
                  gradientUnits="userSpaceOnUse">
    <stop offset="0%" stop-color="#22c55e"/><stop offset="45%" stop-color="#eab308"/>
    <stop offset="100%" stop-color="#ef4444"/>
  </linearGradient>
  <linearGradient id="dolgu{kimlik}" x1="0" y1="{UST:.0f}" x2="0" y2="{UST + ch:.0f}"
                  gradientUnits="userSpaceOnUse">
    <stop offset="0%" stop-color="#ef4444" stop-opacity=".55"/>
    <stop offset="45%" stop-color="#eab308" stop-opacity=".35"/>
    <stop offset="100%" stop-color="#22c55e" stop-opacity=".08"/>
  </linearGradient>
</defs>
{"".join(izgara)}
<line x1="{SOL:.1f}" y1="{UST + ch:.1f}" x2="{SOL + cw:.1f}" y2="{UST + ch:.1f}"
      stroke="var(--axis)" stroke-width="1"/>
{"".join(yollar)}
{"".join(etiketler)}
</svg></div>"""


def _ozet_satiri(noktalar: list[tuple[int, float]], etiket: str) -> str:
    if not noktalar:
        return ""
    degerler = [d for _, d in noktalar]
    return (
        f"<span>{esc(etiket)} tepe <b>{esc(fmt_bps(max(degerler)))}</b></span>"
        f"<span>ortalama <b>{esc(fmt_bps(sum(degerler) / len(degerler)))}</b></span>"
        f"<span>son <b>{esc(fmt_bps(degerler[-1]))}</b></span>"
    )


def sayfa(
    config: dict[str, Any],
    logo: str,
    secili_hostid: str | None = None,
    saat: int = 6,
) -> str:
    """Bir yurdun tüm arayüzleri için trafik grafikleri."""
    now = int(time.time())
    saat = max(1, min(saat, 72))  # 72 saatten fazlası hem yavaş hem okunmaz

    govde = ["<h1>Trafik Grafikleri</h1>"]
    try:
        with ZabbixClient(config["zabbix"]) as z:
            hostlar = sorted(
                z.get_hosts(config["zabbix"]["host_groups"]), key=lambda h: h["name"]
            )
            if not hostlar:
                return _kabuk(logo, "".join(govde) + '<p class="bos">Yurt bulunamadı.</p>')

            secili = next((h for h in hostlar if h["hostid"] == secili_hostid), hostlar[0])
            items = z.get_items([secili["hostid"]])
            arayuzler = _arayuzleri_ayikla(items)

            tum_idler = [i for v in arayuzler.values() for i in (v["in"], v["out"])]
            gecmis = (
                z.get_history(tum_idler, now - saat * 3600, now, value_type=3)
                if tum_idler else {}
            )
    except ZabbixError as exc:
        log.error("Trafik grafiği için Zabbix'e ulaşılamadı: %s", exc)
        return _kabuk(
            logo,
            "".join(govde)
            + f'<p class="bos">Zabbix\'e ulaşılamadı: {esc(str(exc))}</p>',
        )

    secenekler = "".join(
        f'<option value="{esc(h["hostid"])}"{" selected" if h["hostid"] == secili["hostid"] else ""}>'
        f'{esc(h["name"])}</option>'
        for h in hostlar
    )
    saat_secenek = "".join(
        f'<option value="{s}"{" selected" if s == saat else ""}>son {s} saat</option>'
        for s in (1, 3, 6, 12, 24, 48)
    )
    govde.append(
        f'<p class="alt">{esc(secili["name"])} · {len(arayuzler)} arayüz · '
        f'son {saat} saat · veri doğrudan Zabbix geçmişinden</p>'
        f'<form class="tsec" method="GET" action="/trafik">'
        f'<select name="yurt" onchange="this.form.submit()">{secenekler}</select>'
        f'<select name="saat" onchange="this.form.submit()">{saat_secenek}</select>'
        f'<span class="bilgi">Seçim değişince grafik yeniden çizilir.</span></form>'
    )

    if not arayuzler:
        govde.append(
            pages.kart(
                "Arayüz bulunamadı",
                '<p class="bos">Bu yurtta SNMP arayüz keşfi tamamlanmamış; '
                "trafik item'ları yok. Cihazda SNMP servisini ve Zabbix'e izin "
                "veren politikayı kontrol edin.</p>",
            )
        )
        return _kabuk(logo, "".join(govde))

    kartlar = []
    for sira, (ad, idler) in enumerate(arayuzler.items()):
        gelen = gecmis.get(idler["in"], [])
        giden = gecmis.get(idler["out"], [])
        if not gelen and not giden:
            continue
        icerik = cizgi_grafik([("Gelen", gelen), ("Giden", giden)], f"g{sira}")
        icerik += (
            '<div class="gosterge">'
            '<span><i style="background:linear-gradient(90deg,#22c55e,#ef4444)"></i>'
            "Gelen — bits received (dolu çizgi)</span>"
            '<span><i style="background:linear-gradient(90deg,#22c55e,#ef4444);opacity:.6"></i>'
            "Giden — bits sent (kesik çizgi)</span></div>"
            f'<div class="ozet">{_ozet_satiri(gelen, "Gelen")}</div>'
            f'<div class="ozet">{_ozet_satiri(giden, "Giden")}</div>'
        )
        kartlar.append(
            pages.kart(
                f"{_kisa(secili['name'])} — {ad}",
                icerik,
                aciklama=f"{len(gelen)} ölçüm noktası · renk yükseldikçe kırmızıya döner.",
            )
        )

    govde.append(f'<div class="grafikler">{"".join(kartlar)}</div>')
    return _kabuk(logo, "".join(govde))


def _kisa(ad: str) -> str:
    from .reports_html import _kisa_ad

    return _kisa_ad(ad)


def _kabuk(logo: str, govde: str) -> str:
    return pages.shell(
        baslik="Trafik Grafikleri — Yurt İnterneti",
        aktif="/trafik",
        govde=govde,
        logo=logo,
        ek_css=TRAFIK_CSS,
    )
