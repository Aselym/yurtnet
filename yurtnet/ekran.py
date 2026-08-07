"""Duvara asılan televizyon için tam ekran özet.

Normal pano masaüstü içindir: 34 satırlık tablo, filtre kutuları, 13 punto
yazı. Duvarda 3-4 metreden okunmaz. Bu sayfa aynı veriyi uzaktan okunacak
biçimde gösterir.

Üç tasarım kararı:

1. **Sorunlar büyük, sağlıklılar küçük.** Ekrana bakan kişi "her şey yolunda
   mı" sorusunun cevabını bir saniyede almalı; ayrıntı sorun varsa gerekir.
2. **Son güncelleme zamanı büyük yazılır.** Duvardaki bir ekranın en tehlikeli
   hâli sessizce donmasıdır — kimse fark etmez ve herkes eski veriye bakar.
   Veri bayatlarsa saat kırmızıya döner.
3. **Etkileşim yok.** Filtre, düğme, bağlantı konmaz; kimse başında durmuyor.

Ölçüler `vw` biriminde: 1920 ekranda da 3840 ekranda da aynı görünür.
"""

from __future__ import annotations

import time
from typing import Any

from .brand import LOGO_DATA_URI
from .collect import HostSnapshot
from .diagnose import Finding
from .render import esc, fmt_duration

# Bayatlık eşiği: kontrol aralığının bu katı geçilirse saat kırmızıya döner.
BAYAT_KAT = 4

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --zemin:#0b0b0a; --kart:#171715; --kart2:#1e1e1b; --cizgi:#2e2e2a;
  --ink:#fff; --ink2:#b9b8ae; --muted:#7e7c74;
  --iyi:#22c55e; --uyari:#f5b83d; --kritik:#f05a5a;
}
html,body{height:100%}
body{background:var(--zemin);color:var(--ink);overflow:hidden;
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  display:flex;flex-direction:column}

/* ---- üst şerit ---- */
.ust{display:flex;align-items:center;justify-content:space-between;
  padding:1.1vw 2vw 0.9vw;border-bottom:1px solid var(--cizgi);flex:none}
.ust img{height:2.4vw;background:#fff;border-radius:.4vw;padding:.35vw .6vw;display:block}
.baslik{font-size:1.85vw;font-weight:700;letter-spacing:-.02em}
.saat{text-align:right;line-height:1.25}
.saat .t{font-size:2.5vw;font-weight:700;font-variant-numeric:tabular-nums}
.saat .g{font-size:.95vw;color:var(--muted)}
.saat.bayat .t{color:var(--kritik)}
.saat.bayat .g{color:var(--kritik)}

/* ---- KPI bandı ---- */
.bant{display:grid;grid-template-columns:repeat(4,1fr);gap:.9vw;padding:1vw 2vw;flex:none}
.bant .k{background:var(--kart);border:1px solid var(--cizgi);border-radius:.9vw;
  padding:.9vw 1.2vw;display:flex;flex-direction:column;min-width:0}
.bant .e{font-size:1.02vw;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
  font-weight:650;margin-bottom:.45vw}
.bant .n{font-size:3.2vw;font-weight:730;line-height:1;font-variant-numeric:tabular-nums}
.bant .a{font-size:1.02vw;color:var(--ink2);margin-top:.4vw;line-height:1.35}
.bant .k.iyi .n{color:var(--iyi)}
.bant .k.uyari .n{color:var(--uyari)}
.bant .k.kritik .n{color:var(--kritik)}
/* Dikkat gereken yurtların adları: yönetici raporundaki rozetlerin ekran boyu. */
/* Yükseklik sınırı yok: dikkat gereken her yurdun adı görünmeli. Liste
   uzayınca kart büyür, aşağıdaki ızgara kısalır — hangi yurda bakılacağı
   bilgisi, ızgaradaki birkaç satırdan daha değerli. */
.rozetler{display:flex;flex-wrap:wrap;gap:.35vw;margin-top:.55vw;align-content:flex-start}
.rozet{display:inline-flex;align-items:center;gap:.4vw;font-size:1.02vw;
  border:1px solid var(--cizgi);border-radius:1vw;padding:.15vw .6vw .15vw .45vw;
  background:var(--kart2);white-space:nowrap}
.rozet i{width:.55vw;height:.55vw;border-radius:50%;background:var(--uyari);flex:none}
.rozet.kritik i{background:var(--kritik)}

/* ---- sorun kartları ---- */
.orta{flex:1;min-height:0;padding:0 2vw 1vw;display:flex;flex-direction:column;gap:1vw}
.sorunlar{display:grid;gap:.9vw;grid-template-columns:repeat(auto-fit,minmax(27vw,1fr));
  align-content:start;overflow:hidden}
.sorun{background:var(--kart);border-left:.45vw solid var(--kritik);border-radius:.7vw;
  padding:1vw 1.3vw;display:flex;justify-content:space-between;align-items:flex-start;gap:1vw}
.sorun.uyari{border-left-color:var(--uyari)}
.sorun .ad{font-size:1.9vw;font-weight:700;line-height:1.1}
.sorun .bolge{font-size:.95vw;color:var(--muted);margin-top:.25vw}
.sorun .ne{font-size:1.15vw;color:var(--ink2);margin-top:.5vw;line-height:1.35}
.sorun .sure{font-size:1.5vw;font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
.sorun.uyari .sure{color:var(--uyari)}
.sorun .sure{color:var(--kritik)}

/* ---- her şey yolundaysa ----
   flex:none: mesaj kendi boyunda kalır, artan yeri ızgara alır. flex:1
   verildiğinde ekranın yarısı boş bir onay işaretine gidiyordu. */
.temiz{flex:none;display:flex;align-items:center;justify-content:center;
  gap:1.2vw;text-align:left;padding:.6vw 0}
.temiz .isaret{font-size:3.4vw;line-height:1;color:var(--iyi)}
.temiz .yazi{font-size:2.1vw;font-weight:700}
.temiz .alt{font-size:1.15vw;color:var(--muted);margin-top:.2vw}

/* ---- tüm yurtlar ızgarası ----
   flex:1 + grid-auto-rows:1fr — hücreler kalan yüksekliği paylaşır, böylece
   ekran doldu ve yazılar uzaktan okunacak boya çıktı. */
.izgara{display:grid;gap:.5vw;grid-template-columns:repeat(6,1fr);
  flex:1;min-height:0;grid-auto-rows:1fr}
.hucre{background:var(--kart2);border-radius:.5vw;padding:.5vw 1vw;
  display:flex;align-items:center;gap:.8vw;min-width:0}
.hucre .nokta{width:1vw;height:1vw;border-radius:50%;flex:none;background:var(--iyi)}
.hucre.uyari .nokta{background:var(--uyari)}
.hucre.kritik .nokta{background:var(--kritik)}
.hucre.kritik{background:rgba(240,90,90,.16)}
.hucre.uyari{background:rgba(245,184,61,.14)}
.hucre .ad{font-size:1.35vw;color:var(--ink2);white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.hucre.kritik .ad,.hucre.uyari .ad{color:var(--ink);font-weight:650}

/* Yazarın imzası. Uzaktan bakınca okunmaz, ekrana yaklaşınca görünür —
   gizlemek değil, göze batmamak amaçlanıyor. */
.imza{position:fixed;right:.7vw;bottom:.45vw;font-size:.45vw;letter-spacing:.08em;
  color:var(--muted);opacity:.4;user-select:none;pointer-events:none}
"""

SLAYT_CSS = """
/* ---- slayt düzeni ----
   Slaytlar yan yana duruyor, kap kaydırılıyor. Her slayt tam ekran yüksekliğinde
   bir flex sütunu; birinci slaydın iç yerleşimi böylece hiç değişmiyor. */
.slaytlar{display:flex;width:calc(var(--adet) * 100%);height:100%;
  transition:transform .65s cubic-bezier(.4,0,.2,1)}
.slaytlar.gecissiz{transition:none}
.slayt{width:calc(100% / var(--adet));height:100%;flex:none;
  display:flex;flex-direction:column;min-width:0}
.noktalar{position:fixed;left:50%;bottom:.7vw;transform:translateX(-50%);
  display:flex;gap:.5vw;z-index:5}
.noktalar i{width:.55vw;height:.55vw;border-radius:50%;background:var(--muted);
  opacity:.35;transition:opacity .3s,background .3s}
.noktalar i.etkin{opacity:1;background:var(--ink)}
/* Duvardaki ekranda imleç görünmesin; fare oynatılınca geri gelir, çünkü
   tıklayarak slayt değiştirmek isteyenin imleci görmesi gerek. */
body.imlecsiz{cursor:none}
"""

SLAYT_JS = """
// Slayt gösterisi: 10 saniyede bir ilerler, tıklanınca da ilerler.
// Sayfa her dakika kendini yenilediği için hangi slaytta olduğumuz saklanır;
// aksi halde her yenilemede birinci slayda dönüp ikinciyi kimse göremezdi.
(function(){
  var kap=document.getElementById('slaytlar');
  if(!kap) return;
  var adet=kap.querySelectorAll('.slayt').length;
  if(adet<2) return;
  var noktalar=document.getElementById('noktalar');
  var ANAHTAR='yurtnet.slayt', SURE=10000;
  var i=0, zaman=null;
  try{ i=Math.min(parseInt(sessionStorage.getItem(ANAHTAR)||'0',10)||0, adet-1); }catch(e){}

  function ciz(animasyon){
    kap.classList.toggle('gecissiz', !animasyon);
    kap.style.transform='translateX(-'+(i*(100/adet))+'%)';
    if(noktalar) [].forEach.call(noktalar.children,function(n,k){
      n.classList.toggle('etkin', k===i);
    });
    try{ sessionStorage.setItem(ANAHTAR, String(i)); }catch(e){}
    // Geçişsiz çizimden hemen sonra animasyonu geri aç.
    if(!animasyon) requestAnimationFrame(function(){
      requestAnimationFrame(function(){ kap.classList.remove('gecissiz'); });
    });
  }
  function ilerle(){ i=(i+1)%adet; ciz(true); kur(); }
  function kur(){ clearTimeout(zaman); zaman=setTimeout(ilerle, SURE); }

  ciz(false);   // yenileme sonrası aynı slaytta, animasyonsuz devam
  kur();
  document.addEventListener('click', function(){ ilerle(); });

  // İmleç: hareket edince görünür, 3 saniye durunca kaybolur.
  var imlec=null;
  document.body.classList.add('imlecsiz');
  document.addEventListener('mousemove', function(){
    document.body.classList.remove('imlecsiz');
    clearTimeout(imlec);
    imlec=setTimeout(function(){ document.body.classList.add('imlecsiz'); }, 3000);
  });
})();
"""

JS = """
// Saat her saniye ilerler: donmuş bir ekranı fark etmenin en kolay yolu.
// Veri bayatlarsa (sunucu ya da ağ durduysa) saat kırmızıya döner.
(function(){
  var kutu=document.getElementById('saat'), t=document.getElementById('t'),
      uretim=Number(kutu.dataset.uretim), bayat=Number(kutu.dataset.bayat);
  function tik(){
    var d=new Date();
    t.textContent=String(d.getHours()).padStart(2,'0')+':'
                 +String(d.getMinutes()).padStart(2,'0')+':'
                 +String(d.getSeconds()).padStart(2,'0');
    var yas=(Date.now()/1000)-uretim;
    kutu.classList.toggle('bayat', yas>bayat);
  }
  tik(); setInterval(tik,1000);
})();

"""


def _kisa(ad: str) -> str:
    """TUGVA-KIRSEHIR-AHI-T25 -> Kırşehir Ahi. Ekranda cihaz modeli işe yaramaz."""
    from .reports_html import _kisa_ad

    return _kisa_ad(ad)


# 7 günlük özet, ekran her dakika çizildiği için önbelleklenir. Veritabanı
# doldukça bu sorgu saniyeler sürebiliyor ve rakamlar dakikalık tazelik
# gerektirmiyor; anlık durum zaten bulgulardan geliyor.
_ozet_cache: tuple[float, dict] | None = None


def _ozet(store, config: dict[str, Any], now: int) -> dict:
    """Yönetici raporundaki KPI değerleri: çalışma oranı, kesinti, dikkat listesi."""
    global _ozet_cache
    omur = int(config["poll"].get("report_refresh_minutes", 10)) * 60
    if _ozet_cache and (now - _ozet_cache[0]) < omur:
        return _ozet_cache[1]

    from .reports_html import IZLEME_KODLARI, siniflandir
    from .store import KESINTI_KODLARI, ariza_suresi

    v = store.weekly_stats(now - 7 * 86400, now)
    hosts = v["hosts"]
    olaylar = [i for i in v["incidents"] if i.code not in IZLEME_KODLARI]
    sinif = siniflandir(
        olaylar, now,
        int(config["report"].get("onemli_sure_dakika", 10)) * 60,
        int(config["report"].get("tekrar_esigi", 4)),
    )
    dikkat = [h for h in hosts if h["hostid"] in sinif["dikkat_hostlari"]]
    sonuc = {
        "uptime": sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0,
        "kesinti": sum(ariza_suresi(i, now) for i in olaylar if i.code in KESINTI_KODLARI),
        "toplam": len(hosts),
        "dikkat": [(_kisa(h["name"]), h["hostid"]) for h in dikkat],
        "acik_hostlar": {i.hostid for i in sinif["acik"] if i.hostid},
    }
    _ozet_cache = (now, sonuc)
    return sonuc


def _durum(bulgular: list[Finding]) -> str:
    for seviye, ad in (("critical", "kritik"), ("warning", "uyari")):
        if any(f.severity == seviye for f in bulgular):
            return ad
    return "iyi"


def _bant(store, config, now, snapshots, sayim, durumlar) -> tuple[str, int]:
    """Yönetici raporundaki dört KPI kartının ekran boyu karşılığı.

    "Şu anda süren sorun" değeri rapordan değil anlık bulgulardan gelir:
    duvardaki ekran o andaki gerçeği göstermeli, ayrıca aşağıdaki ızgarayla
    aynı sayıyı söylemeli. Arıza kaydı teyit turları yüzünden birkaç dakika
    geriden gelir ve iki farklı rakam çıkardı.
    """
    from .render import fmt_pct

    kritik, uyari = sayim["kritik"], sayim["uyari"]
    # Not, kritik olmayıp uyarı olan durumu da söylemeli: aşağıda sarı bir kart
    # dururken "0 · ağ çalışır durumda" yazması çelişkili görünüyordu.
    if kritik:
        durum_notu = "müdahale bekliyor"
    elif uyari:
        durum_notu = f"kritik yok · {uyari} yurt uyarı veriyor"
    else:
        durum_notu = "ağ çalışır durumda"
    kart4 = (
        f'<div class="k {"kritik" if kritik else ("uyari" if uyari else "iyi")}">'
        f'<div class="e">şu anda süren sorun</div>'
        f'<div class="n">{kritik}</div>'
        f'<div class="a">{durum_notu} · {sayim["iyi"]}/{len(snapshots)} yurt normal</div></div>'
    )

    if store is None:
        return f'<div class="bant" style="grid-template-columns:1fr">{kart4}</div>', 0

    try:
        o = _ozet(store, config, now)
    except Exception:
        return f'<div class="bant" style="grid-template-columns:1fr">{kart4}</div>', 0

    # Tamamı basılır, kaçının görüneceğine tarayıcı ölçerek karar verir.
    # Açık sorunu olanlar başta: kırpılacak olanlar en az acil olanlar olsun.
    sirali_dikkat = sorted(o["dikkat"], key=lambda d: d[1] not in o["acik_hostlar"])
    rozetler = "".join(
        f'<span class="rozet{" kritik" if hid in o["acik_hostlar"] else ""}">'
        f"<i></i>{esc(ad)}</span>"
        for ad, hid in sirali_dikkat
    )

    return f"""<div class="bant">
  <div class="k"><div class="e">başarılı çalışma oranı</div>
    <div class="n">{esc(fmt_pct(o["uptime"], 2))}</div>
    <div class="a">son 7 günün ortalaması</div></div>
  <div class="k"><div class="e">toplam kesinti</div>
    <div class="n">{esc(fmt_duration(o["kesinti"]))}</div>
    <div class="a">tüm yurtlar toplamı</div></div>
  <div class="k"><div class="e">dikkat gereken yurt</div>
    <div class="n">{len(o["dikkat"])} / {o["toplam"]}</div>
    <div class="rozetler">{rozetler or '<span class="a">yok</span>'}</div></div>
  {kart4}
</div>""", len(o["dikkat"])


def render(
    snapshots: list[HostSnapshot],
    findings_by_host: dict[str, list[Finding]],
    regional: list[Finding],
    config: dict[str, Any],
    store=None,
    now: int | None = None,
) -> str:
    now = now or int(time.time())
    aralik = int(config["poll"].get("check_interval_minutes", 1)) * 60

    durumlar = {s.hostid: _durum(findings_by_host.get(s.hostid, [])) for s in snapshots}
    sayim = {"iyi": 0, "uyari": 0, "kritik": 0}
    for d in durumlar.values():
        sayim[d] += 1

    bant, dikkat_sayisi = _bant(store, config, now, snapshots, sayim, durumlar)

    # Sorunlu yurtlar: önce kritik, sonra uyarı; her birinde en ağır bulgu yazılır.
    sirali = sorted(
        (s for s in snapshots if durumlar[s.hostid] != "iyi"),
        key=lambda s: (durumlar[s.hostid] != "kritik", s.name.lower()),
    )

    # Ne kadardır sürdüğünü arıza kaydından alıyoruz; anlık bulgu bunu bilmiyor.
    baslangic: dict[str, int] = {}
    if store is not None:
        try:
            for i in store.acik_incidentlar():
                if i.hostid and i.code not in ("NO_IF_DATA", "STALE_DATA"):
                    baslangic[i.hostid] = min(baslangic.get(i.hostid, i.started_at), i.started_at)
        except Exception:
            pass

    kartlar = []
    for s in sirali[:8]:  # 8'den fazlası ekrana sığmaz, okunaklılık bozulur
        bulgular = findings_by_host.get(s.hostid, [])
        en_agir = next(
            (f for f in bulgular if f.severity == "critical"),
            next((f for f in bulgular if f.severity == "warning"), None),
        )
        sure = ""
        if s.hostid in baslangic:
            sure = fmt_duration(now - baslangic[s.hostid])
        kartlar.append(
            f'<div class="sorun {durumlar[s.hostid]}">'
            f'<div><div class="ad">{esc(_kisa(s.name))}</div>'
            f'<div class="bolge">{esc(s.region)}</div>'
            f'<div class="ne">{esc(en_agir.title if en_agir else "—")}</div></div>'
            f'<div class="sure">{esc(sure)}</div></div>'
        )

    if kartlar:
        artan = len(sirali) - len(kartlar)
        ek = (
            f'<div class="temiz" style="flex:none;font-size:1vw;color:var(--muted)">'
            f"ve {artan} yurt daha</div>" if artan > 0 else ""
        )
        orta = f'<div class="sorunlar">{"".join(kartlar)}</div>{ek}'
    else:
        orta = (
            '<div class="temiz"><div class="isaret">✓</div><div>'
            f'<div class="yazi">{len(snapshots)} yurdun tamamı çalışıyor</div>'
            '<div class="alt">Müdahale bekleyen sorun yok</div></div></div>'
        )

    hucreler = "".join(
        f'<div class="hucre {durumlar[s.hostid]}"><span class="nokta"></span>'
        f'<span class="ad">{esc(_kisa(s.name))}</span></div>'
        for s in sorted(snapshots, key=lambda s: _kisa(s.name).lower())
    )
    # Dikkat listesi uzayınca üstteki kart büyüyor ve ızgaraya az yer kalıyor.
    # Satırlar içeriklerinden kısalamadığı için alttakiler kırpılıyordu; sütun
    # sayısını artırmak satır sayısını düşürüp hepsinin görünmesini sağlıyor.
    # 20'yi geçtiğinde hiçbir sütun düzeni yetmiyor — ama o noktada ızgara zaten
    # gereksiz, çünkü yurtların çoğu yukarıdaki listede adıyla yazılı. Yarım
    # kırpılmış bir ızgara göstermektense hiç gösterilmiyor.
    sutun = 6 if dikkat_sayisi <= 12 else 9
    izgara = (
        f'<div class="izgara" style="grid-template-columns:repeat({sutun},1fr)">'
        f"{hucreler}</div>"
        if dikkat_sayisi <= 20
        else ""
    )

    bolgesel = "".join(
        f'<div class="sorun kritik" style="grid-column:1/-1">'
        f'<div><div class="ad">{esc(f.title)}</div></div></div>'
        for f in regional
    )

    # İkinci slayt tali içerik: üretilemezse birinci slayt tek başına gösterilir.
    try:
        from . import ekran_trafik

        slayt2 = ekran_trafik.slayt(config, snapshots, durumlar, now)
        slayt2_css = ekran_trafik.CSS
    except Exception:
        log.exception("Trafik slaydı üretilemedi — ekran tek slayt gösterilecek.")
        slayt2, slayt2_css = "", ""

    ikinci = f'<section class="slayt">{slayt2}</section>' if slayt2 else ""
    noktalar = (
        '<div class="noktalar" id="noktalar"><i class="etkin"></i><i></i></div>'
        if slayt2 else ""
    )

    return f"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="{aralik}">
<title>Yurt İnternet Durumu — Ekran</title>
<style>{CSS}{SLAYT_CSS}{slayt2_css}</style>
</head><body>
<div class="slaytlar" id="slaytlar" style="--adet:{2 if slayt2 else 1}">
<section class="slayt">
<header class="ust">
  <img src="{LOGO_DATA_URI}" alt="Piramit Bilgisayar">
  <div class="baslik">YURT İNTERNET DURUMU</div>
  <div class="saat" id="saat" data-uretim="{now}" data-bayat="{aralik * BAYAT_KAT}">
    <div class="t" id="t">--:--:--</div>
    <div class="g">son güncelleme {time.strftime('%H:%M', time.localtime(now))}</div>
  </div>
</header>

{bant}

<main class="orta">
  {bolgesel}
  {orta}
  {izgara}
</main>
</section>
{ikinci}
</div>
{noktalar}
<div class="imza">aselym</div>
<script>{JS}{SLAYT_JS}</script>
</body></html>
"""
