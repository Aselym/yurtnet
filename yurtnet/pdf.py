"""Aylık yönetici raporunu PDF olarak üretir — koyu tema, iki sayfa.

Neden HTML→PDF dönüştürücü değil: WeasyPrint/wkhtmltopdf sisteme GTK gibi ağır
bağımlılıklar getiriyor ve Windows'ta kurulamadığı için geliştirme makinesinde
test edilemiyor. fpdf2 saf Python — iki platformda aynı çıktı, kurulum
`pip install fpdf2` ile bitiyor.

Koyu tema kullanıcı tercihi: bu rapor ekranda okunuyor ve paylaşılıyor,
kağıda basılmıyor. Basılacak olsaydı açık zemin daha doğru olurdu.

Sayfa 1 — özet ve grafikler. Sayfa 2 — yurt detayı ve öne çıkanlar.
Ölçüler milimetre.
"""

from __future__ import annotations

import base64
import datetime as dt
import io
import logging
import math
import os
import time
from typing import Any

from fpdf import FPDF

from .brand import LOGO_DATA_URI
from .render import fmt_duration, fmt_pct, fmt_time
from .reports_html import (
    IZLEME_KODLARI,
    YONETICI_DILI,
    _gun_etiketi_kisa,
    _hafta_etiketi,
    _kisa_ad,
    siniflandir,
    sorunlu_zaman,
)
from .store import KESINTI_KODLARI, Store, ariza_suresi

log = logging.getLogger(__name__)

# ---- koyu tema paleti ----
ZEMIN = (17, 17, 16)
KART = (28, 28, 26)
KART2 = (36, 36, 33)
CIZGI = (52, 52, 48)
INK = (255, 255, 255)
INK2 = (198, 197, 188)
MUTED = (138, 136, 128)
SERI = (77, 155, 240)
SERI_SOLUK = (32, 64, 104)
IYI = (34, 197, 94)
UYARI = (245, 184, 61)
KRITIK = (239, 90, 90)
BEYAZ = (255, 255, 255)


# Türkçe için Unicode font şart; yerleşik Helvetica Latin-1 ve "ı ş ğ İ" bozulur.
# Microsoft fontları sunucuya kopyalanmaz (lisans), her platform kendi fontunu kullanır.
FONT_ADAYLARI = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
]

SOL, EN = 13.0, 184.0  # sol kenar ve kullanılabilir genişlik
ALT = 283.0            # alt bilgi çizgisi


def _font_bul() -> tuple[str, str] | None:
    for normal, kalin in FONT_ADAYLARI:
        if os.path.exists(normal) and os.path.exists(kalin):
            return normal, kalin
    return None


def _logo_bytes() -> io.BytesIO:
    return io.BytesIO(base64.b64decode(LOGO_DATA_URI.split(",", 1)[1]))


class Rapor(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(False)
        self.set_margins(SOL, 12, SOL)
        yollar = _font_bul()
        if yollar:
            self.add_font("g", "", yollar[0])
            self.add_font("g", "B", yollar[1])
            self.f = "g"
        else:
            log.warning(
                "Unicode font bulunamadı, Türkçe karakterler bozulabilir. "
                "Ubuntu'da: sudo apt install fonts-dejavu-core"
            )
            self.f = "helvetica"

    # ---------------------------------------------------------------- temel

    def yeni_sayfa(self):
        self.add_page()
        self.set_fill_color(*ZEMIN)
        self.rect(0, 0, 210, 297, style="F")

    def yazi(self, x, y, metin, boy=9, kalin=False, renk=INK, hiza="L", en=None):
        self.set_font(self.f, "B" if kalin else "", boy)
        self.set_text_color(*renk)
        self.set_xy(x, y)
        self.cell(en if en is not None else 0, boy * 0.42, metin, align=hiza)

    def cizgi(self, x1, y1, x2, y2, renk=CIZGI, kalinlik=0.2):
        self.set_draw_color(*renk)
        self.set_line_width(kalinlik)
        self.line(x1, y1, x2, y2)

    def dolu(self, x, y, en, boy, renk, yaricap=0.9):
        self.set_fill_color(*renk)
        self.rect(x, y, en, max(boy, 0.1), style="F", round_corners=True, corner_radius=yaricap)

    def kart(self, x, y, en, boy, baslik=None, ipucu=None):
        self.set_fill_color(*KART)
        self.set_draw_color(*CIZGI)
        self.set_line_width(0.25)
        self.rect(x, y, en, boy, style="DF", round_corners=True, corner_radius=2.4)
        if baslik:
            self.yazi(x + 5, y + 4.6, baslik.upper(), 6.8, True, MUTED)
        if ipucu:
            self.yazi(x + en - 5, y + 4.6, ipucu, 6.4, False, MUTED, "R", 0)

    def rozet(self, x, y, metin, renk, boy=4.6):
        """Koyu zeminde rozet: rengin koyu tonu zemin, canlı tonu yazı."""
        self.set_font(self.f, "B", 6.8)
        en = self.get_string_width(metin) + 4.4
        self.set_fill_color(*[int(c * 0.3 + z * 0.7) for c, z in zip(renk, KART)])
        self.rect(x, y, en, boy, style="F", round_corners=True, corner_radius=boy / 2)
        self.yazi(x + 2.2, y + boy / 2 - 1.2, metin, 6.8, True, renk)
        return en

    # ------------------------------------------------------------- grafikler

    def halka(self, cx, cy, dis, ic, dilimler):
        toplam = sum(d for _, d, _ in dilimler) or 1
        aci = -90.0
        for _, deger, renk in dilimler:
            if deger <= 0:
                continue
            genislik = deger / toplam * 360
            self.set_fill_color(*renk)
            if genislik >= 359.9:
                self.ellipse(cx - dis, cy - dis, dis * 2, dis * 2, style="F")
                self.set_fill_color(*KART)
                self.ellipse(cx - ic, cy - ic, ic * 2, ic * 2, style="F")
            else:
                adim = max(3, int(genislik / 2.5))
                n = []
                for i in range(adim + 1):
                    a = math.radians(aci + genislik * i / adim)
                    n.append((cx + dis * math.cos(a), cy + dis * math.sin(a)))
                for i in range(adim, -1, -1):
                    a = math.radians(aci + genislik * i / adim)
                    n.append((cx + ic * math.cos(a), cy + ic * math.sin(a)))
                self.set_draw_color(*renk)
                self.set_line_width(0.1)
                self.polygon(n, style="DF")
            aci += genislik

    def cubuklar(self, x, y, en, veriler, birim="", satir=6.6, renk=SERI):
        """Yatay çubuk listesi: etiket · çubuk · değer."""
        if not veriler:
            self.yazi(x, y, "Veri yok.", 8, False, MUTED)
            return
        buyuk = max(d for _, d in veriler) or 1
        etiket_en, deger_en = en * 0.40, 17.0
        cubuk_en = en - etiket_en - deger_en - 3
        for etiket, deger in veriler:
            self.yazi(x, y + 1.3, etiket, 7.8, False, INK2)
            cx = x + etiket_en
            self.dolu(cx, y + 1.8, cubuk_en, 2.6, SERI_SOLUK, 1.3)
            self.dolu(cx, y + 1.8, max(1.4, cubuk_en * deger / buyuk), 2.6, renk, 1.3)
            self.yazi(x + en - deger_en, y + 1.3, f"{deger:g}{birim}", 7.8, True, INK, "R", deger_en)
            y += satir

    def sutunlar(self, x, y, en, boy, veriler, bicim=str, bosluk_etiket=True):
        """Sıfırdan başlayan sütun grafiği. None değer = ölçüm yok."""
        olcum = [d for _, d in veriler if d is not None]
        if not olcum:
            self.yazi(x, y + boy / 2, "Bu dönemde veri yok.", 8, False, MUTED)
            return
        buyuk = max(olcum) or 1
        n = len(veriler)
        # Az sütun varsa (yeni kurulumda birkaç günlük veri) bantlar dar kalıp
        # grafiği boş gösteriyordu; sütun sayısı azaldıkça kalınlık artıyor.
        bant = min(en / n, 30.0)
        x = x + (en - bant * n) / 2
        kalin = min(16.0, bant * 0.52 if n > 8 else bant * 0.62)
        taban = y + boy
        self.cizgi(x, taban, x + bant * n, taban, CIZGI, 0.3)
        buyuk_i = max(range(n), key=lambda i: (veriler[i][1] or 0))
        for i, (etiket, deger) in enumerate(veriler):
            merkez = x + i * bant + bant / 2
            if deger is None:
                self.set_draw_color(*CIZGI)
                self.set_line_width(0.25)
                self.set_dash_pattern(dash=1, gap=1)
                self.rect(merkez - kalin / 2, taban - 6, kalin, 6)
                self.set_dash_pattern()
            elif deger > 0:
                h = (deger / buyuk) * (boy - 6)
                self.dolu(merkez - kalin / 2, taban - h, kalin, h, SERI, 1.0)
                if n <= 10 or i == buyuk_i:
                    self.yazi(merkez - bant / 2, taban - h - 4.0, bicim(deger), 6.8, True,
                              INK, "C", bant)
            else:
                self.dolu(merkez - kalin / 2, taban - 0.7, kalin, 0.7, CIZGI, 0.3)
            if bosluk_etiket and (n <= 12 or i % max(1, n // 9) == 0):
                self.yazi(merkez - bant / 2, taban + 1.8, etiket, 6.4, False, MUTED, "C", bant)


# ============================================================ veri toplama


def _veri(store: Store, config: dict[str, Any], now: int, gun: int = 30) -> dict:
    since = now - gun * 86400
    v = store.weekly_stats(since, now)
    hosts = v["hosts"]
    tum = v["incidents"]
    incidents = [i for i in tum if i.code not in IZLEME_KODLARI]
    sinif = siniflandir(
        incidents, now,
        int(config["report"].get("onemli_sure_dakika", 10)) * 60,
        int(config["report"].get("tekrar_esigi", 4)),
    )
    tipler: dict[str, int] = {}
    for i in incidents:
        ad = YONETICI_DILI.get(i.code, i.code)
        tipler[ad] = tipler.get(ad, 0) + 1
    return {
        "since": since,
        "gun": gun,
        "hosts": hosts,
        "incidents": incidents,
        "izleme_eksigi": sorted({i.name for i in tum if i.code in IZLEME_KODLARI and i.name}),
        "sinif": sinif,
        "tipler": sorted(tipler.items(), key=lambda x: -x[1]),
        "uptime": sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0,
        "kesinti": sum(
            ariza_suresi(i, now) for i in incidents if i.code in KESINTI_KODLARI
        ),
        "sorunlu": [h for h in hosts if h["hostid"] in sinif["dikkat_hostlari"]],
        "zaman": sorunlu_zaman(incidents, hosts, now),
        "gunler": store.daily_summary(since, now),
        "seri": store.haftalik_seri(8, now),
    }


def _bolge_gecikme(hosts: list[dict]) -> list[tuple[str, float]]:
    toplam: dict[str, dict[str, float]] = {}
    for h in hosts:
        if not h.get("avg_latency"):
            continue
        a = h.get("checks") or 1
        t = toplam.setdefault(h["region"], {"t": 0.0, "a": 0.0})
        t["t"] += h["avg_latency"] * a
        t["a"] += a
    return sorted(((b, round(v["t"] / v["a"], 1)) for b, v in toplam.items()), key=lambda x: x[1])


def _dakika(d: float) -> str:
    return fmt_duration(int(d) * 60)


AY_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
           "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def _gun_ay_etiketi(gun_str: str) -> str:
    try:
        g = dt.date.fromisoformat(gun_str)
        return f"{g.day} {AY_KISA[g.month - 1]}"
    except Exception:
        return gun_str


# ================================================================== sayfalar


def _ust_bant(p: Rapor, d: dict, now: int, altbaslik: str) -> float:
    """Başlık bandı: yalnızca başlık, tarih aralığı ve logo.

    Durum rozeti buradan kaldırıldı — sayfanın en tepesinde "sorun var"
    uyarısıyla açılmasın istendi; durum zaten KPI kartlarında ve tabloda var.
    """
    p.yazi(SOL, 14, "Aylık Yönetici Raporu", 19, True)

    tarih = f"{fmt_time(d['since'])} – {fmt_time(now)} · {altbaslik}"
    p.yazi(SOL, 23.4, tarih, 8, False, MUTED)

    logo_en = 32.0
    logo_boy = logo_en * 135 / 440
    p.dolu(SOL + EN - logo_en - 3, 12.5, logo_en + 6, logo_boy + 4, BEYAZ, 1.6)
    try:
        p.image(_logo_bytes(), x=SOL + EN - logo_en, y=14.5, w=logo_en)
    except Exception:
        pass
    p.cizgi(SOL, 30.5, SOL + EN, 30.5, CIZGI, 0.4)
    return 36.0


def _kpi(p: Rapor, y: float, d: dict, ara_bosluk: float) -> float:
    boy, ara = 25.0, 3.5
    kutu = (EN - 3 * ara) / 4
    acik = d["sinif"]["acik"]
    kartlar = [
        (fmt_pct(d["uptime"], 2), "Başarılı çalışma oranı", f"son {d['gun']} günün ortalaması", INK),
        (fmt_duration(d["kesinti"]), "Toplam kesinti", "tüm yurtlar toplamı", INK),
        (f"{len(d['sorunlu'])}/{len(d['hosts'])}", "Dikkat gereken yurt",
         "süren veya tekrarlayan", INK),
        (str(len(acik)), "Şu anda süren sorun",
         "müdahale bekliyor" if acik else "devam eden sorun yok",
         KRITIK if acik else IYI),
    ]
    for i, (deger, etiket, notu, renk) in enumerate(kartlar):
        x = SOL + i * (kutu + ara)
        p.kart(x, y, kutu, boy)
        p.yazi(x + 5, y + 4.8, etiket.upper(), 6.2, True, MUTED)
        p.yazi(x + 5, y + 10.4, deger, 16, True, renk)
        p.yazi(x + 5, y + 19.4, notu, 6.4, False, INK2)
    return y + boy + ara_bosluk


def _durum_ve_bolge(p: Rapor, y: float, store: Store, d: dict, boy: float,
                    ara_bosluk: float) -> float:
    yarim = (EN - 5) / 2
    # sol: halka
    p.kart(SOL, y, yarim, boy, "Yurtların şu anki durumu")
    sev = store.acik_incident_severity()
    kritik = sum(1 for h in d["hosts"] if sev.get(h["hostid"]) == "critical")
    uyari = sum(1 for h in d["hosts"] if sev.get(h["hostid"]) == "warning")
    dilimler = [
        ("Normal çalışıyor", len(d["hosts"]) - kritik - uyari, IYI),
        ("Uyarı", uyari, UYARI),
        ("Kritik", kritik, KRITIK),
    ]
    cy = y + boy / 2 + 3
    p.halka(SOL + 22, cy, 15, 9.4, dilimler)
    p.yazi(SOL + 12, cy - 2.6, str(len(d["hosts"])), 14, True, INK, "C", 20)
    p.yazi(SOL + 12, cy + 3.4, "yurt", 6.4, False, MUTED, "C", 20)
    ly = cy - 10
    for ad, deger, renk in dilimler:
        p.dolu(SOL + 43, ly + 0.7, 2.6, 2.6, renk, 0.7)
        p.yazi(SOL + 47.5, ly, ad, 7.8, False, INK2)
        p.yazi(SOL + 43, ly, str(deger), 7.8, True, INK, "R", yarim - 48)
        ly += 6.8

    # sağ: bölge gecikmesi
    x2 = SOL + yarim + 5
    p.kart(x2, y, yarim, boy, "Bölgelere göre yanıt süresi", "düşük = iyi")
    bolgeler = _bolge_gecikme(d["hosts"])
    p.cubuklar(x2 + 5, y + 11, yarim - 10, bolgeler, " ms",
               min(7.0, (boy - 15) / max(1, len(bolgeler))))
    return y + boy + ara_bosluk


def _egilim_ve_tipler(p: Rapor, y: float, d: dict, boy: float, ara_bosluk: float) -> float:
    yarim = (EN - 5) / 2
    p.kart(SOL, y, yarim, boy, "Son 8 haftanın eğilimi", "olay sayısı")
    seri = [(_hafta_etiketi(h["bitis"]), (h["olay"] if h["veri_var"] else None)) for h in d["seri"]]
    p.sutunlar(SOL + 5, y + 11, yarim - 10, boy - 19, seri)

    x2 = SOL + yarim + 5
    p.kart(x2, y, yarim, boy, "Sorunlar ne kaynaklı", "olay")
    if d["tipler"]:
        p.cubuklar(x2 + 5, y + 11, yarim - 10, [(a, n) for a, n in d["tipler"][:5]], "",
                   min(6.6, (boy - 15) / max(1, len(d["tipler"][:5]))))
    else:
        p.yazi(x2 + 5, y + boy / 2, "Bu dönemde sorun yaşanmadı.", 8, False, MUTED)
    return y + boy + ara_bosluk


def _gunluk(p: Rapor, y: float, d: dict, yukseklik: float) -> float:
    p.kart(SOL, y, EN, yukseklik, "Günlük kesinti süresi",
           "tüm yurtlarda toplam, gün gün")
    # Bir aylık grafikte gün numarası yeter; birkaç günlük veri varsa çıplak
    # "4 5 6" anlamsız görünüyor, ay kısaltması ekleniyor.
    etiket = _gun_etiketi_kisa if len(d["gunler"]) > 10 else _gun_ay_etiketi
    gunluk = [(etiket(g["gun"]), round((g["kesinti_sure"] or 0) / 60))
              for g in d["gunler"]]
    if any(v for _, v in gunluk):
        p.sutunlar(SOL + 5, y + 11, EN - 10, yukseklik - 19, gunluk, _dakika)
    else:
        p.yazi(SOL + 5, y + yukseklik / 2, "Bu dönemde kesinti yaşanmadı.", 8, False, MUTED)
    return y + yukseklik + 5


def _tablo(p: Rapor, y: float, d: dict, now: int, satir_sayisi: int) -> float:
    zaman, sinif = d["zaman"], d["sinif"]
    basliklar = ("Yurt", "Bölge", "Durum", "Yaşanan sorunlar", "Sorunlu geçen zaman",
                 "Son olay", "Çalışma oranı")
    oranlar = (0.155, 0.115, 0.115, 0.215, 0.175, 0.125, 0.10)
    xs, acc = [], SOL + 5
    for o in oranlar:
        xs.append(acc)
        acc += EN * o - 10 * o

    satir_boy = 10.5
    boy = 19 + satir_boy * max(1, satir_sayisi)
    p.kart(SOL, y, EN, boy, "En çok sorun yaşayan yurtlar",
           "izlendiği sürenin yüzdesine göre")

    ty = y + 12
    for ad, x in zip(basliklar, xs):
        hiza = "R" if ad == "Çalışma oranı" else "L"
        p.yazi(x if hiza == "L" else SOL + EN - 5 - 18, ty, ad.upper(), 6.0, True, MUTED,
               hiza, 18 if hiza == "R" else None)
    ty += 4.4
    p.cizgi(SOL + 5, ty, SOL + EN - 5, ty, CIZGI, 0.3)
    ty += 2.4

    if not d["sorunlu"]:
        p.yazi(SOL + 5, ty + 3, "Bu dönemde kayda değer sorun yaşanmadı.", 8, False, MUTED)
        return y + boy + 5

    acik = {i.hostid for i in sinif["acik"] if i.hostid}
    izleme = {h for h, _ in sinif["tekrarlayan"]}
    sirali = sorted(d["sorunlu"], key=lambda h: -(zaman.get(h["hostid"], {}).get("oran") or 0))
    sirali = sirali[:satir_sayisi]
    buyuk = max(((zaman.get(h["hostid"], {}).get("oran") or 0) for h in sirali), default=1) or 1

    tipler_yurt: dict[str, list[str]] = {}
    for i in d["incidents"]:
        if i.hostid:
            ad = YONETICI_DILI.get(i.code, i.code)
            if ad not in tipler_yurt.setdefault(i.hostid, []):
                tipler_yurt[i.hostid].append(ad)

    for sira, h in enumerate(sirali):
        b = zaman.get(h["hostid"], {})
        oran = b.get("oran")
        if h["hostid"] in acik:
            renk, yazi = KRITIK, "Devam ediyor"
        elif h["hostid"] in izleme:
            renk, yazi = UYARI, "İzlemede"
        else:
            renk, yazi = IYI, "Çözüldü"

        p.yazi(xs[0], ty + 3.0, _kisa_ad(h["name"])[:18], 7.8, True, INK)
        p.yazi(xs[1], ty + 3.0, h["region"][:12], 7.4, False, MUTED)
        p.rozet(xs[2], ty + 2.0, yazi, renk, 4.4)

        sorunlar = tipler_yurt.get(h["hostid"], [])
        sutun_en = xs[4] - xs[3] - 3
        p.yazi(xs[3], ty + 1.6, _sigdir(p, sorunlar[0] if sorunlar else "—", sutun_en, 7.2),
               7.2, False, INK2)
        if len(sorunlar) > 1:
            ek = ", ".join(sorunlar[1:])
            p.yazi(xs[3], ty + 5.8, _sigdir(p, ek, sutun_en, 6.4), 6.4, False, MUTED)

        cubuk_en = EN * 0.13
        p.dolu(xs[4], ty + 2.2, cubuk_en, 2.4, SERI_SOLUK, 1.2)
        p.dolu(xs[4], ty + 2.2, max(1.2, cubuk_en * (oran or 0) / buyuk), 2.4, SERI, 1.2)
        p.yazi(xs[4], ty + 5.8, f"%{oran:.2f}" if oran is not None else "—", 6.6, False, INK2)

        if b.get("acik"):
            p.rozet(xs[5], ty + 2.0, "Şu anda sürüyor", KRITIK, 4.4)
        elif b.get("son"):
            gecen = now - b["son"]
            tz = IYI if gecen > 43200 else (UYARI if gecen > 7200 else KRITIK)
            p.rozet(xs[5], ty + 2.0, f"{fmt_duration(gecen)} önce", tz, 4.4)
        else:
            p.yazi(xs[5], ty + 3.0, "—", 7.4, False, MUTED)

        p.yazi(SOL + EN - 5 - 18, ty + 3.0, fmt_pct(h["uptime_pct"], 2), 7.8, True, INK, "R", 18)

        ty += satir_boy
        if sira < len(sirali) - 1:
            p.cizgi(SOL + 5, ty - 1.4, SOL + EN - 5, ty - 1.4, (40, 40, 37), 0.2)
    return y + boy + 5


def _ozet(p: Rapor, y: float, d: dict, boy: float | None = None) -> float:
    """Maddeler. Yükseklik multi_cell'in gerçek çıktısından ilerletilir;
    sabit adım kullanılınca iki satırlık maddeler bir sonrakiyle çakışıyordu."""
    maddeler = _maddeler(d)
    if boy is None:
        boy = _ozet_yuksekligi(p, maddeler)
    p.kart(SOL, y, EN, boy, "Öne çıkanlar")
    my = y + 11.5
    for m in maddeler:
        p.dolu(SOL + 6, my + 1.5, 1.6, 1.6, SERI, 0.8)
        p.set_font(p.f, "", 8)
        p.set_text_color(*INK2)
        p.set_xy(SOL + 10, my - 0.8)
        p.multi_cell(EN - 16, 4.2, m, align="L")
        my = p.get_y() + 2.2
    return y + boy + 5


def _ozet_yuksekligi(p: Rapor, maddeler: list[str]) -> float:
    p.set_font(p.f, "", 8)
    toplam = 11.5
    for m in maddeler:
        satir = len(p.multi_cell(EN - 16, 4.2, m, align="L", dry_run=True, output="LINES"))
        toplam += satir * 4.2 + 2.2
    return toplam + 3


def _sigdir(p: Rapor, metin: str, en: float, punto: float) -> str:
    """Metni verilen genişliğe kırpar; kelime ortasından kesik bırakmaz."""
    p.set_font(p.f, "", punto)
    if p.get_string_width(metin) <= en:
        return metin
    while metin and p.get_string_width(metin + "…") > en:
        metin = metin[:-1]
    return metin.rstrip(" ,") + "…"


def _tum_yurtlar(p: Rapor, y: float, d: dict, store: Store, boy: float) -> float:
    """Filonun tamamı, üç sütunlu kompakt liste.

    Yönetici raporu ilk beşi gösteriyor; burası "peki diğerleri ne durumda"
    sorusunu cevaplıyor. İkinci sayfanın boş kalan alanını da bu doldurur.
    """
    p.kart(SOL, y, EN, boy, "Tüm yurtlar", "çalışma oranı · son 30 gün")
    sev = store.acik_incident_severity()
    sirali = sorted(d["hosts"], key=lambda h: (h["uptime_pct"], h["name"]))

    sutun = 3
    ic_en = (EN - 12) / sutun
    satir_boy = 5.6
    basi = y + 12
    kullanilabilir = boy - 15
    satir_sayisi = max(1, int(kullanilabilir / satir_boy))

    for i, h in enumerate(sirali[: satir_sayisi * sutun]):
        kol, sat = divmod(i, satir_sayisi)
        x = SOL + 6 + kol * ic_en
        ty = basi + sat * satir_boy
        durum = sev.get(h["hostid"])
        renk = KRITIK if durum == "critical" else (UYARI if durum == "warning" else IYI)
        p.dolu(x, ty + 1.0, 1.8, 1.8, renk, 0.9)
        p.yazi(x + 4, ty, _sigdir(p, _kisa_ad(h["name"]), ic_en - 30, 7.2), 7.2, False, INK2)
        p.yazi(x + ic_en - 26, ty, fmt_pct(h["uptime_pct"], 2), 7.2, True, INK, "R", 20)
    return y + boy + 5


def _maddeler(d: dict) -> list[str]:
    m: list[str] = []
    surekli = [h for h in d["sorunlu"] if h["uptime_pct"] < 50]
    if surekli:
        m.append(
            f"{', '.join(_kisa_ad(h['name']) for h in surekli)} dönem boyunca büyük "
            "ölçüde erişilemez durumdaydı; yerinde müdahale gerekiyor."
        )
    tekrar = d["sinif"]["tekrarlayan"]
    if tekrar:
        adlar = {h["hostid"]: _kisa_ad(h["name"]) for h in d["hosts"]}
        ilk = sorted(tekrar.items(), key=lambda x: -len(x[1]))[:3]
        m.append(
            ", ".join(adlar.get(hid, "") for (hid, _), _ in ilk)
            + " yurtlarında sorun tekrar ediyor; her seferinde kendiliğinden düzeldiği "
            "için şikâyet gelmemiş olabilir, kontrol edilmeli."
        )
    onemsiz = d["sinif"]["onemsiz"]
    if onemsiz:
        m.append(
            f"Ayrıca {len(onemsiz)} kısa dalgalanma yaşandı ve hepsi birkaç dakika içinde "
            "kendiliğinden düzeldi; müdahale gerektirmez."
        )
    if d["izleme_eksigi"]:
        m.append(
            f"{len(d['izleme_eksigi'])} yurtta izleme eksiği var "
            f"({', '.join(_kisa_ad(a) for a in d['izleme_eksigi'])}). Bu yurtlarda internet "
            "çalışıyor; ölçemediğimiz şey ne kadar trafik geçtiği."
        )
    if not m:
        m.append("Bu dönemde öne çıkan bir sorun yok, ağ istikrarlı çalıştı.")
    return m[:4]


def _alt_bilgi(p: Rapor, d: dict, now: int, sayfa: str) -> None:
    p.cizgi(SOL, ALT, SOL + EN, ALT)
    p.yazi(SOL, ALT + 2.6, f"{len(d['hosts'])} yurt · son {d['gun']} gün · {sayfa}",
           6.6, False, MUTED)
    p.yazi(SOL, ALT + 2.6, f"yurtnet · {fmt_time(now)}", 6.6, False, MUTED, "R", EN)


# ==================================================================== giriş


def uret(store: Store, config: dict[str, Any], gun: int = 30, now: int | None = None) -> bytes:
    """Aylık yönetici raporu, iki sayfalık PDF."""
    now = now or int(time.time())
    d = _veri(store, config, now, gun)
    p = Rapor()

    # ---- sayfa 1: özet ve grafikler ----
    p.yeni_sayfa()
    y = _ust_bant(p, d, now, "genel bakış")
    # Blok yükseklikleri sabit; artan alan aralara eşit dağıtılır. Kalanı tek
    # bir kutuya vermek denendi ve günlük grafik sayfanın yarısını kaplıyordu.
    h_kpi, h_durum, h_egilim, h_gunluk = 25.0, 56.0, 50.0, 58.0
    kalan = (ALT - 6) - y - (h_kpi + h_durum + h_egilim + h_gunluk)
    ara = max(4.0, min(14.0, kalan / 4))
    y = _kpi(p, y, d, ara)
    y = _durum_ve_bolge(p, y, store, d, h_durum, ara)
    y = _egilim_ve_tipler(p, y, d, h_egilim, ara)
    _gunluk(p, y, d, h_gunluk)
    _alt_bilgi(p, d, now, "sayfa 1/2")

    # ---- sayfa 2: yurt detayı ----
    p.yeni_sayfa()
    y = _ust_bant(p, d, now, "yurt detayı")
    ozet_boy = _ozet_yuksekligi(p, _maddeler(d))
    satir = min(8, max(1, len(d["sorunlu"])))
    tablo_boy = 19 + 10.5 * satir
    # Kalan alan "tüm yurtlar" listesine gider; sabit yükseklik verilirse
    # sayfanın alt yarısı boş kalıyor.
    kalan = (ALT - 6) - y - tablo_boy - ozet_boy - 10
    y = _tablo(p, y, d, now, satir)
    if kalan >= 30:
        y = _tum_yurtlar(p, y, d, store, kalan)
    _ozet(p, y, d, ozet_boy)
    _alt_bilgi(p, d, now, "sayfa 2/2")

    return bytes(p.output())
