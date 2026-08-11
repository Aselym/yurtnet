"""Teknik servis raporu — üç bölüm.

1. **Arıza kaydı**    — Zabbix'in açık trigger'ları + yurtnet'in kendi kayıtları
2. **Tekrarlayan**    — aynı yurtta yinelenen sorunlar, saat dağılımıyla
3. **Analiz**         — ölçüm geçmişinden çıkarılan süregelen eğilimler

Üç bölümdeki her kayıt elle **kapatılabilir**. Kapatma silme değildir: kayıt
yerinde kalır, yalnız listeden düşer. Kapatıldıktan sonra aynı sorun tekrar
ederse liste onu geri getirir — aksi halde bir kez kapatılan sorun bir daha
görünmez ve sessizce büyür.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from . import analiz, pages
from .render import esc, fmt_duration, fmt_time
from .report import CODE_LABEL
from .store import Store

log = logging.getLogger(__name__)

# Zabbix'in kendi önem dereceleri (problem.get -> severity).
ZABBIX_SEVIYE = {
    "0": ("notr", "Sınıflandırılmamış"), "1": ("notr", "Bilgi"),
    "2": ("uyari", "Uyarı"), "3": ("ciddi", "Orta"),
    "4": ("kritik", "Yüksek"), "5": ("kritik", "Felaket"),
}

# Zabbix trigger metinleri İngilizce ve teknik. Servise bakan herkesin
# ezberlemesini beklemek yerine her uyarının karşılığı burada yazılı.
# Eşleşme küçük harfe indirgenip parça arayarak yapılıyor: arayüz adı
# (eth1, sw10...) metnin içinde değiştiği için tam eşitlik işe yaramaz.
ZABBIX_ACIKLAMA = [
    ("unavailable by icmp ping",
     "Cihaz ping'e cevap vermiyor — yurt internete erişemiyor. "
     "ISP kesintisi, elektrik kesintisi ya da cihaz arızası."),
    ("high icmp ping loss",
     "Paketlerin bir kısmı kayboluyor. Bağlantı kopmuyor ama görüşmeler "
     "donuyor, sayfalar takılıyor — genellikle hat kalitesi sorunu."),
    ("high icmp ping response time",
     "Ping yanıt süresi normalin üzerinde. Hat doluysa kapasite, değilse "
     "ISP yönlendirmesi kaynaklıdır."),
    ("no snmp data collection",
     "Cihaz SNMP sorgularına cevap vermiyor. İnternet çalışıyor olabilir; "
     "ölçemediğimiz şey trafik ve arayüz bilgisi. Bu bir izleme eksiğidir."),
    ("host has been restarted",
     "Cihazın çalışma süresi sıfırlanmış. Elektrik kesintisi, güç sorunu, "
     "firmware güncellemesi ya da kilitlenme olabilir."),
    ("link down",
     "Arayüz fiziksel olarak kapandı. Kablo çıkmış, SFP arızalı ya da "
     "karşı taraftaki port kapanmış olabilir."),
    ("high bandwidth usage",
     "Arayüz kapasitesinin büyük kısmı kullanılıyor. Arıza değil, kapasite "
     "sorunu — yavaşlık şikâyetlerinin en sık sebebi."),
    ("high error rate",
     "Arayüzde hatalı paket oranı yüksek. Fiziksel katman sorununa işaret "
     "eder: kablo, SFP, patch ya da duplex uyuşmazlığı."),
    ("changed to lower speed",
     "Bağlantı hızı düşmüş (ör. 1 Gb'den 100 Mb'ye). Kablo/port sorunu ya da "
     "karşı taraftaki ayar değişikliği."),
    ("system name has changed",
     "Cihazın sistem adı değişmiş. Genellikle yapılandırma değişikliğidir, "
     "arıza değildir."),
]


def _zabbix_aciklama(baslik: str) -> str:
    kucuk = (baslik or "").lower()
    for parca, aciklama in ZABBIX_ACIKLAMA:
        if parca in kucuk:
            return aciklama
    return ""


_zabbix_onbellek: tuple[float, list[dict]] | None = None
ZABBIX_ONBELLEK_SN = 120


def _zabbix_uyarilari(config: dict[str, Any], now: int) -> list[dict[str, Any]]:
    """Zabbix'te o an açık olan problemler (trigger'lar).

    Kendi ön tanımızdan bağımsız: Zabbix ne diyorsa o. Servis ekibi zaten
    Zabbix'e bakıyor; iki ekranda iki farklı gerçek olmasın diye buraya da
    aynısı konuyor.
    """
    global _zabbix_onbellek
    if _zabbix_onbellek and (now - _zabbix_onbellek[0]) < ZABBIX_ONBELLEK_SN:
        return _zabbix_onbellek[1]

    from .zabbix import ZabbixClient

    try:
        with ZabbixClient(config["zabbix"]) as z:
            hostlar = z.get_hosts(config["zabbix"]["host_groups"])
            adlar = {h["hostid"]: h["name"] for h in hostlar}
            problemler = z.get_problems(list(adlar))
            eslesme = z.map_events_to_hosts(problemler)
    except Exception:
        log.exception("Zabbix uyarıları alınamadı")
        return _zabbix_onbellek[1] if _zabbix_onbellek else []

    satirlar = []
    for hostid, olaylar in eslesme.items():
        for o in olaylar:
            satirlar.append({
                "eventid": o.get("eventid", ""),
                "hostid": hostid,
                "ad": adlar.get(hostid, hostid),
                "baslik": (o.get("name") or "").replace("Network Generic Device: ", ""),
                "severity": str(o.get("severity", "0")),
                "clock": int(o.get("clock", 0)),
                "onaylandi": o.get("acknowledged") == "1",
                "bastirildi": o.get("suppressed") == "1",
            })
    satirlar.sort(key=lambda x: (-int(x["severity"]), x["clock"]))
    _zabbix_onbellek = (now, satirlar)
    return satirlar


# ------------------------------------------------------------------ yardımcı


def _kapali_mi(kapatilanlar: dict, bolum: str, anahtar: str, son_olay: int) -> bool:
    """Kayıt kapatılmış sayılır mı.

    Kapatma zamanından SONRA yeni bir olay olduysa kapatma düşer; sorun geri
    gelmiştir ve görünmelidir.
    """
    k = kapatilanlar.get((bolum, anahtar))
    return bool(k) and son_olay <= k["kapatan"]


def _kapat_dugmesi(bolum: str, anahtar: str, baslik: str) -> str:
    return (
        f'<form class="kapat-f" method="POST" action="/kapat">'
        f'<input type="hidden" name="bolum" value="{esc(bolum)}">'
        f'<input type="hidden" name="anahtar" value="{esc(anahtar)}">'
        f'<input type="hidden" name="baslik" value="{esc(baslik[:120])}">'
        f'<button type="submit" title="Bu kaydı listeden düşür">Kapat</button></form>'
    )


def _saat_grafigi(saatler: dict[int, int]) -> str:
    """24 saatlik dağılım — sorunun günün hangi saatinde çıktığını gösterir."""
    if not saatler:
        return ""
    tepe = max(saatler.values()) or 1
    cubuklar = "".join(
        f'<i style="height:{max(2, saatler.get(h, 0) / tepe * 22):.0f}px'
        f'{";opacity:.18" if not saatler.get(h) else ""}" '
        f'title="{h:02d}:00 — {saatler.get(h, 0)} kez"></i>'
        for h in range(24)
    )
    yogun = max(saatler.items(), key=lambda x: x[1])
    return (
        f'<div class="saatler">{cubuklar}</div>'
        f'<div class="saat-not">en sık {yogun[0]:02d}:00 ({yogun[1]} kez) · '
        f'0–24 saat dağılımı</div>'
    )


# ------------------------------------------------------------------ bölümler


def _bolum1(store: Store, config: dict, incidents: list, kapatilanlar: dict,
            now: int) -> tuple[str, int]:
    uyarilar = _zabbix_uyarilari(config, now)
    goster = [u for u in uyarilar if not _kapali_mi(kapatilanlar, "zabbix", u["eventid"], u["clock"])]
    gizli = len(uyarilar) - len(goster)

    if goster:
        satirlar = []
        for u in goster:
            kod, ad = ZABBIX_SEVIYE.get(u["severity"], ("notr", u["severity"]))
            rozetler = pages.rozet(kod, ad)
            if u["onaylandi"]:
                rozetler += " " + pages.rozet("iyi", "Onaylandı")
            if u["bastirildi"]:
                rozetler += " " + pages.rozet("notr", "Bastırıldı")
            satirlar.append(
                f"<tr><td><strong>{esc(_kisa(u['ad']))}</strong>"
                f'<div class="sonuk" style="font-size:11.5px">{esc(u["ad"])}</div></td>'
                f"<td>{esc(u['baslik'])}"
                + (f'<div class="zbx-ac">{esc(_zabbix_aciklama(u["baslik"]))}</div>'
                   if _zabbix_aciklama(u["baslik"]) else "")
                + f"</td><td>{rozetler}</td>"
                f'<td class="sayi sonuk">{esc(fmt_time(u["clock"]))}</td>'
                f'<td class="sayi">{esc(fmt_duration(now - u["clock"]))}</td>'
                f'<td>{_kapat_dugmesi("zabbix", u["eventid"], u["ad"] + " — " + u["baslik"])}</td></tr>'
            )
        zabbix_tablo = (
            '<div class="sar"><table><tr><th>Yurt</th><th>Zabbix uyarısı</th>'
            "<th>Önem</th><th>Başlangıç</th><th>Süre</th><th></th></tr>"
            + "".join(satirlar) + "</table></div>"
        )
    elif uyarilar:
        zabbix_tablo = '<p class="bos">Açık uyarıların tamamı kapatılmış.</p>'
    else:
        zabbix_tablo = '<p class="bos">Zabbix\'te açık uyarı yok.</p>'

    if gizli:
        zabbix_tablo += f'<p class="ipucu">{gizli} uyarı elle kapatıldığı için gizlendi.</p>'

    from .reports_html import _servis_kayitlari

    return (
        pages.kart(
            "1 · Arıza kaydı — Zabbix uyarıları",
            zabbix_tablo,
            aciklama=(
                "Zabbix'te o an açık olan trigger'lar. Kendi ön tanımızdan bağımsız, "
                "doğrudan Zabbix'ten okunur — servis ekibi iki ekranda farklı şey görmesin."
            ),
        )
        + pages.kart(
            "1 · Arıza kaydı — yurtnet dökümü",
            # Katlanmış duruyor: yüzlerce kayıtla açık bırakıldığında sayfanın
            # tamamını kaplayıp 2. ve 3. bölümü görünmez kılıyordu.
            f'<details class="dokum"><summary>{len(incidents)} kaydın tam dökümünü aç</summary>'
            f"{_servis_kayitlari(store, incidents, config, now)}</details>",
            aciklama=(
                "yurtnet'in kendi ölçümlerinden ürettiği kayıtlar. Satıra tıklayınca "
                "tam teknik döküm açılır: sebep, ölçümün geldiği item, aşılan eşik ve "
                "kaydın açıldığı andaki hat değerleri."
            ),
        )
    ), len(goster)


def _bolum2(store: Store, config: dict, kapatilanlar: dict, now: int) -> tuple[str, int]:
    rc = config.get("report", {})
    sessiz = int(rc.get("tekrar_sessiz_gun", 2))
    tekrarlar = store.tekrarlayan_sorunlar(
        now, gun=30, sessiz_gun=sessiz, en_az=int(rc.get("tekrar_en_az", 2))
    )
    goster = [t for t in tekrarlar
              if not _kapali_mi(kapatilanlar, "tekrar", t["dedup_key"], t["son"])]
    gizli = len(tekrarlar) - len(goster)

    if not goster:
        icerik = (
            '<p class="bos">Tekrar eden sorun yok.</p>' if not tekrarlar
            else '<p class="bos">Tekrar eden sorunların tamamı kapatılmış.</p>'
        )
    else:
        kartlar = []
        for t in goster:
            son_olaylar = "".join(
                f"<li>{esc(fmt_time(o['started_at']))}"
                + (f" — {esc(fmt_duration(o['ended_at'] - o['started_at']))}"
                   if o["ended_at"] else " — <strong>sürüyor</strong>")
                + "</li>"
                for o in t["son_olaylar"][:6]
            )
            durum = pages.rozet("kritik", "Şu an açık") if t["acik"] else pages.rozet(
                "uyari", f"{fmt_duration(now - t['son'])} önce")
            kartlar.append(
                f'<div class="tekrar">'
                f'<div class="tekrar-bas">'
                f'<div><span class="tekrar-ad">{esc(_kisa(t["name"]))}</span>'
                f'<span class="sonuk"> · {esc(t["region"] or "—")}</span>'
                f'<div class="tekrar-kod">{esc(CODE_LABEL.get(t["code"], t["code"]))}'
                f' <code>{esc(t["code"])}</code></div></div>'
                f'<div class="tekrar-sag"><span class="tekrar-adet">{t["adet"]}<small> kez</small></span>'
                f'{_kapat_dugmesi("tekrar", t["dedup_key"], (t["name"] or "") + " " + t["code"])}</div></div>'
                f'<div class="tekrar-alt">{durum} '
                f'<span class="sonuk">toplam {esc(fmt_duration(t["toplam_sure"] or 0))} sürdü · '
                f'ilk {esc(fmt_time(t["ilk"]))}</span></div>'
                f'{_saat_grafigi(t["saatler"])}'
                f'<details><summary>son olaylar</summary><ul>{son_olaylar}</ul></details>'
                f"</div>"
            )
        icerik = f'<div class="tekrarlar">{"".join(kartlar)}</div>'

    if gizli:
        icerik += f'<p class="ipucu">{gizli} kayıt elle kapatıldığı için gizlendi.</p>'

    return pages.kart(
        "2 · Tekrarlayan sorunlar",
        icerik,
        aciklama=(
            f"Son 30 günde aynı yurtta yinelenen sorunlar; kaç kez ve günün hangi "
            f"saatlerinde çıktığı görünür. Liste her açılışta yeniden hesaplanır. "
            f"{sessiz} gün boyunca tekrar etmeyen sorun listeden kendiliğinden düşer."
        ),
    ), len(goster)


def _bolum3(store: Store, config: dict, kapatilanlar: dict, now: int) -> tuple[str, int]:
    sonuc = analiz.calistir(store, config, now)
    bulgular = sonuc["bulgular"]
    goster = [b for b in bulgular if not _kapali_mi(kapatilanlar, "analiz", b["kimlik"], now)]
    gizli = len(bulgular) - len(goster)

    if sonuc.get("hata"):
        icerik = '<p class="bos">Analiz üretilemedi; sunucu günlüğüne bakın.</p>'
    elif not goster:
        icerik = (
            f'<p class="bos">Süregelen bir eğilim tespit edilmedi. '
            f'({sonuc["gun"]} günlük ölçüm incelendi.)</p>' if not bulgular
            else '<p class="bos">Bulguların tamamı kapatılmış.</p>'
        )
    else:
        kartlar = []
        for b in goster:
            vade = pages.rozet("kritik" if b["vade"] == "uzun" else "uyari",
                               "Uzun vadeli" if b["vade"] == "uzun" else "Kısa vadeli")
            kartlar.append(
                f'<div class="bulgu {esc(b["tur"])}">'
                f'<div class="bulgu-bas"><div>'
                f'<div class="bulgu-baslik">{esc(b["baslik"])}</div>'
                f'<div class="bulgu-yurt">{esc(b["ad"])}'
                f'<span class="sonuk"> · {esc(b["bolge"] or "—")}</span></div></div>'
                f'<div class="tekrar-sag">{vade}'
                f'{_kapat_dugmesi("analiz", b["kimlik"], b["ad"] + " — " + b["baslik"])}'
                f"</div></div>"
                f'<p class="bulgu-ayrinti">{esc(b["ayrinti"])}</p>'
                f'<p class="bulgu-kanit">{esc(b["kanit"])}</p>'
                f"</div>"
            )
        icerik = f'<div class="bulgular">{"".join(kartlar)}</div>'

    if gizli:
        icerik += f'<p class="ipucu">{gizli} bulgu elle kapatıldığı için gizlendi.</p>'

    return pages.kart(
        "3 · Analiz",
        icerik,
        aciklama=(
            f"Ölçüm geçmişinden çıkarılan süregelen eğilimler — tek tek bakınca eşiği "
            f"aşmayan ama günlerdir devam eden bozulmalar. Her yurt kendi geçmişiyle "
            f"kıyaslanır, sabit eşikle değil. İncelenen veri: son {sonuc['gun']} gün."
        ),
    ), len(goster)


def _kapatilanlar_karti(store: Store, kapatilanlar: dict) -> str:
    if not kapatilanlar:
        return ""
    ad = {"zabbix": "Zabbix uyarısı", "tekrar": "Tekrarlayan", "analiz": "Analiz"}
    satirlar = "".join(
        f"<tr><td class=\"sonuk\">{esc(ad.get(k[0], k[0]))}</td>"
        f"<td>{esc(v.get('baslik') or k[1])}</td>"
        f'<td class="sayi sonuk">{esc(fmt_time(v["kapatan"]))}</td>'
        f'<td><form class="kapat-f" method="POST" action="/kapat">'
        f'<input type="hidden" name="bolum" value="{esc(k[0])}">'
        f'<input type="hidden" name="anahtar" value="{esc(k[1])}">'
        f'<input type="hidden" name="islem" value="geri">'
        f'<button type="submit" class="geri">Geri al</button></form></td></tr>'
        for k, v in sorted(kapatilanlar.items(), key=lambda x: -x[1]["kapatan"])
    )
    return pages.kart(
        "Kapatılan kayıtlar",
        '<div class="sar"><table><tr><th>Bölüm</th><th>Kayıt</th>'
        "<th>Kapatıldı</th><th></th></tr>" + satirlar + "</table></div>",
        aciklama=(
            "Kapatma silme değildir. Kayıt yerinde durur, yalnız listeden düşer — "
            "ve aynı sorun tekrar ederse kendiliğinden geri gelir."
        ),
    )


def _kisa(ad: str | None) -> str:
    from .reports_html import _kisa_ad
    return _kisa_ad(ad)


# ------------------------------------------------------------------- sayfa


def sayfa(store: Store, config: dict[str, Any], logo: str, now: int | None = None) -> str:
    now = now or int(time.time())
    from .reports_html import IZLEME_KODLARI, _hafta

    v = _hafta(store, config, now)
    incidents = v["incidents"]
    kapatilanlar = store.kapatilanlar()

    acik = sum(1 for i in incidents if i.ended_at is None)
    izleme = sum(1 for i in incidents if i.code in IZLEME_KODLARI)

    b1, n1 = _bolum1(store, config, incidents, kapatilanlar, now)
    b2, n2 = _bolum2(store, config, kapatilanlar, now)
    b3, n3 = _bolum3(store, config, kapatilanlar, now)

    govde = [
        "<h1>Teknik Servis Raporu</h1>",
        f'<p class="alt">{esc(fmt_time(v["since"]))} – {esc(fmt_time(now))} · '
        f'{len(v["hosts"])} yurt · {len(incidents)} arıza kaydı ({acik} açık, '
        f'{izleme} izleme eksiği) · kontrol aralığı '
        f'{config["poll"]["check_interval_minutes"]} dk</p>',
        _secici(n1, n2, n3, len(kapatilanlar)),
        f'<div class="bolum" data-bolum="1">{b1}</div>',
        f'<div class="bolum" data-bolum="2">{b2}</div>',
        f'<div class="bolum" data-bolum="3">{b3}</div>',
        f'<div class="bolum" data-bolum="k">{_kapatilanlar_karti(store, kapatilanlar)}</div>',
    ]

    from .reports_html import SERVIS_CSS

    return pages.shell(
        baslik="Teknik Servis Raporu — Yurt İnterneti",
        aktif="/teknik",
        govde="\n".join(govde),
        logo=logo,
        ek_css=SERVIS_CSS + CSS,
    ).replace("</body>", SECICI_JS + "</body>")


def _secici(n1: int, n2: int, n3: int, nk: int) -> str:
    """Bölüm seçici.

    Sayfa uzun; servise bakan kişi çoğu zaman tek bir bölümle ilgileniyor.
    Düğmedeki sayı, o bölümde kaç kayıt olduğunu tıklamadan gösterir.
    """
    dugmeler = [("hepsi", "Tümü", None), ("1", "1 · Arıza kaydı", n1),
                ("2", "2 · Tekrarlayan", n2), ("3", "3 · Analiz", n3)]
    if nk:
        dugmeler.append(("k", "Kapatılanlar", nk))
    parcalar = []
    for kod, ad, say in dugmeler:
        sinif = ' class="etkin"' if kod == "hepsi" else ""
        rozet = f'<span class="sayi-rozet">{say}</span>' if say is not None else ""
        parcalar.append(
            f'<button type="button" data-hedef="{esc(kod)}"{sinif}>{esc(ad)}{rozet}</button>'
        )
    return '<div class="secici" id="secici">' + "".join(parcalar) + "</div>"


SECICI_JS = """
<script>
// Bölüm seçici. Sayfa her 10 dakikada bir yeniden üretildiği için seçim
// saklanıyor; aksi halde kullanıcı baktığı bölümden habersizce "Tümü"ye döner.
(function(){
  var kap=document.getElementById('secici');
  if(!kap) return;
  var ANAHTAR='yurtnet.teknik.bolum';
  var dugmeler=[].slice.call(kap.querySelectorAll('button'));
  var bolumler=[].slice.call(document.querySelectorAll('.bolum'));
  function uygula(hedef){
    bolumler.forEach(function(b){
      b.style.display=(hedef==='hepsi'||b.dataset.bolum===hedef)?'':'none';
    });
    dugmeler.forEach(function(d){ d.classList.toggle('etkin', d.dataset.hedef===hedef); });
    try{ sessionStorage.setItem(ANAHTAR,hedef); }catch(e){}
  }
  dugmeler.forEach(function(d){
    d.addEventListener('click',function(){ uygula(d.dataset.hedef); window.scrollTo(0,0); });
  });
  var kayitli='hepsi';
  try{ kayitli=sessionStorage.getItem(ANAHTAR)||'hepsi'; }catch(e){}
  // Kayıtlı bölüm bu sefer yoksa (ör. kapatılan kalmadı) Tümü'ye düş.
  if(!dugmeler.some(function(d){return d.dataset.hedef===kayitli;})) kayitli='hepsi';
  uygula(kayitli);
})();
</script>
"""


CSS = """
/* ---- bolum secici ---- */
.secici{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}
.secici button{font-family:inherit;font-size:13px;font-weight:600;padding:9px 15px;
  border-radius:8px;border:1px solid var(--line);background:var(--surface);
  color:var(--ink2);cursor:pointer;display:inline-flex;align-items:center;gap:7px}
.secici button:hover{color:var(--ink);border-color:var(--axis)}
.secici button.etkin{background:var(--seri);border-color:var(--seri);color:#fff}
.sayi-rozet{font-size:11px;font-weight:700;background:rgba(128,128,128,.22);
  border-radius:9px;padding:1px 7px;font-variant-numeric:tabular-nums}
.secici button.etkin .sayi-rozet{background:rgba(255,255,255,.25)}

/* ---- katlanır döküm ---- */
.dokum > summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--seri);
  padding:9px 0;user-select:none}
.dokum > summary:hover{text-decoration:underline}
.dokum[open] > summary{margin-bottom:8px}

/* ---- Zabbix uyarısının Türkçe karşılığı ---- */
.zbx-ac{font-size:11.5px;color:var(--muted);line-height:1.5;margin-top:4px;max-width:52ch}

/* ---- kapatma düğmesi ---- */
.kapat-f{display:inline;margin:0}
.kapat-f button{font-family:inherit;font-size:11.5px;font-weight:600;padding:4px 11px;
  border-radius:6px;border:1px solid var(--line);background:transparent;
  color:var(--muted);cursor:pointer;white-space:nowrap}
.kapat-f button:hover{color:var(--ink);border-color:var(--axis)}
.kapat-f button.geri{color:var(--seri);border-color:var(--seri)}
.kapat-f button.geri:hover{background:var(--seri);color:#fff}

/* ---- 2. bölüm: tekrarlayan ---- */
.tekrarlar{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}
.tekrar{background:var(--plane);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.tekrar-bas{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.tekrar-ad{font-size:15px;font-weight:650}
.tekrar-kod{font-size:12px;color:var(--ink2);margin-top:3px}
.tekrar-kod code{font-size:11px}
.tekrar-sag{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.tekrar-adet{font-size:22px;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}
.tekrar-adet small{font-size:11px;font-weight:500;color:var(--muted)}
.tekrar-alt{margin-top:10px;font-size:12px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.saatler{display:flex;align-items:flex-end;gap:2px;height:24px;margin-top:12px}
.saatler i{flex:1;background:var(--seri);border-radius:1px;display:block}
.saat-not{font-size:11px;color:var(--muted);margin-top:5px}
.tekrar details{margin-top:10px;font-size:12px}
.tekrar summary{cursor:pointer;color:var(--muted)}
.tekrar ul{margin:8px 0 0;padding-left:18px;line-height:1.7;color:var(--ink2)}

/* ---- 3. bölüm: analiz ---- */
.bulgular{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(380px,1fr))}
.bulgu{background:var(--plane);border:1px solid var(--line);border-left:3px solid var(--seri);
  border-radius:10px;padding:14px 16px}
.bulgu.yavaslik{border-left-color:var(--uyari)}
.bulgu.kopma{border-left-color:var(--kritik)}
.bulgu.doluluk{border-left-color:var(--ciddi)}
.bulgu-bas{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.bulgu-baslik{font-size:15px;font-weight:650;line-height:1.35}
.bulgu-yurt{font-size:12.5px;color:var(--ink2);margin-top:4px}
.bulgu-ayrinti{font-size:13px;line-height:1.6;color:var(--ink2);margin:10px 0 0}
.bulgu-kanit{font-size:11.5px;color:var(--muted);margin:8px 0 0;font-variant-numeric:tabular-nums}
"""
