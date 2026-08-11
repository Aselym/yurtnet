"""Ölçüm geçmişinden eğilim çıkarımı — teknik servis raporunun analiz bölümü.

Arıza kaydı "şu an ne oluyor" sorusunu, tekrar listesi "aynı şey kaç kez oldu"
sorusunu cevaplıyor. Burası üçüncüsü: **"bir süredir devam eden ne var"**.
Tek tek bakınca eşiği aşmayan, ama günlerdir süren bozulmaları yakalar:

    "5 gündür internet yavaşlığı var"
    "7 gündür akşam saatlerinde hat yoğunlaşıyor"
    "eth1 üzerinde 1 aydır ara ara ping kopuyor"

Üç tasarım kuralı:

1. **Kendi geçmişiyle kıyaslanır, sabit eşikle değil.** 60 ms bir yurtta normal,
   başka yurtta iki katı demektir. Her yurdun kendi taban değeri çıkarılır.
2. **Veri yetmiyorsa bulgu üretilmez.** Üç günlük veriyle "1 aydır" denemez;
   her analizin asgari gün şartı var ve karşılanmazsa sessizce atlanır.
3. **Cümle kurulur, rakam yığılmaz.** Servise bakan kişi ne olduğunu okur;
   dayanak rakamlar yanında küçük punto durur.
"""

from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

# Analiz 30 günlük pencereye bakar; ölçüm tablosu büyüdükçe sorgu ağırlaşır ve
# eğilim rakamlarının dakikalık tazeliğe ihtiyacı yok.
PENCERE_GUN = 30
ONBELLEK_SN = 600

_onbellek: tuple[float, list[dict]] | None = None


def _gun_sayisi(conn, since: int) -> int:
    r = conn.execute(
        "SELECT COUNT(DISTINCT date(ts,'unixepoch','localtime')) g"
        " FROM measurements WHERE ts > ?", (since,)
    ).fetchone()
    return r["g"] or 0


def _ortanca(degerler: list[float]) -> float:
    if not degerler:
        return 0.0
    s = sorted(degerler)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _yavaslik(conn, since: int, now: int, esik_ms: float) -> list[dict]:
    """Gecikmesi kendi tabanının belirgin üstünde seyreden yurtlar.

    Ardışık gün sayılır: dün iyi olduysa "5 gündür" denemez.
    """
    rows = conn.execute(
        "SELECT hostid, name, region, date(ts,'unixepoch','localtime') AS gun,"
        "       AVG(latency_ms) AS ort, COUNT(*) AS n"
        " FROM measurements"
        " WHERE ts > ? AND planned = 0 AND reachable = 1 AND latency_ms IS NOT NULL"
        " GROUP BY hostid, gun HAVING n >= 30 ORDER BY hostid, gun",
        (since,),
    ).fetchall()

    gunluk: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = gunluk.setdefault(r["hostid"], {"ad": r["name"], "bolge": r["region"], "gunler": []})
        g["gunler"].append((r["gun"], r["ort"]))

    bulgular = []
    for hostid, g in gunluk.items():
        gunler = g["gunler"]
        if len(gunler) < 5:
            continue  # taban çıkarmaya yetmez
        taban = _ortanca([o for _, o in gunler])
        if taban <= 0:
            continue
        sinir = max(taban * 1.4, esik_ms)
        # Bugünden geriye doğru kaç gün üst üste sınırın üstünde
        ardisik, son_ort = 0, 0.0
        for gun, ort in reversed(gunler):
            if ort >= sinir:
                ardisik += 1
                son_ort = son_ort or ort
            else:
                break
        if ardisik < 3:
            continue
        bulgular.append({
            "kimlik": f"yavaslik:{hostid}",
            "hostid": hostid, "ad": g["ad"], "bolge": g["bolge"],
            "tur": "yavaslik",
            "vade": "uzun" if ardisik >= 7 else "kisa",
            "baslik": f"{ardisik} gündür internet yavaşlığı",
            "ayrinti": (
                f"Gecikme {ardisik} gündür üst üste bu yurdun normalinin üzerinde. "
                f"Kullanıcı tarafında sayfaların geç açılması, görüntülü görüşmenin "
                f"donması şeklinde hissedilir."
            ),
            "kanit": f"son {ardisik} gün ort. {son_ort:.0f} ms · bu yurdun tabanı {taban:.0f} ms",
        })
    return bulgular


def _saat_yogunlugu(conn, since: int, gun_sayisi: int) -> list[dict]:
    """Trafiğin belirli saat aralığında toplanması.

    Bir yurdun akşam yoğunlaşması normaldir; burada aranan, yoğunluğun günün
    geneline göre BELİRGİN biçimde ayrışması.
    """
    if gun_sayisi < 5:
        return []
    rows = conn.execute(
        "SELECT hostid, name, region,"
        "       CAST(strftime('%H', ts,'unixepoch','localtime') AS INTEGER) AS saat,"
        "       AVG(COALESCE(in_bps,0) + COALESCE(out_bps,0)) AS ort, COUNT(*) AS n"
        " FROM measurements WHERE ts > ? AND planned = 0"
        "   AND (in_bps IS NOT NULL OR out_bps IS NOT NULL)"
        " GROUP BY hostid, saat HAVING n >= 20",
        (since,),
    ).fetchall()

    saatlik: dict[str, dict[str, Any]] = {}
    for r in rows:
        s = saatlik.setdefault(r["hostid"], {"ad": r["name"], "bolge": r["region"], "saatler": {}})
        s["saatler"][r["saat"]] = r["ort"]

    bulgular = []
    for hostid, s in saatlik.items():
        saatler = s["saatler"]
        if len(saatler) < 18:  # günün büyük kısmı ölçülmemişse yorum yapma
            continue
        genel = sum(saatler.values()) / len(saatler)
        if genel <= 0:
            continue
        yogun = sorted(h for h, v in saatler.items() if v >= genel * 1.6)
        if len(yogun) < 2:
            continue
        # Ardışık saatleri tek bir banda topla, en uzun bandı al
        bantlar, mevcut = [], [yogun[0]]
        for h in yogun[1:]:
            (mevcut.append(h) if h == mevcut[-1] + 1 else (bantlar.append(mevcut), mevcut := [h]))
        bantlar.append(mevcut)
        bant = max(bantlar, key=len)
        if len(bant) < 2:
            continue
        tepe = max(saatler[h] for h in bant)
        bulgular.append({
            "kimlik": f"yogunluk:{hostid}",
            "hostid": hostid, "ad": s["ad"], "bolge": s["bolge"],
            "tur": "yogunluk",
            "vade": "uzun" if gun_sayisi >= 7 else "kisa",
            "baslik": f"{gun_sayisi} gündür {bant[0]:02d}:00–{bant[-1] + 1:02d}:00 arası yoğunlaşıyor",
            "ayrinti": (
                "Trafik günün geri kalanına göre bu saatlerde belirgin şekilde artıyor. "
                "Şikâyetler bu aralıkta yoğunlaşıyorsa sebebi kapasite olabilir."
            ),
            "kanit": (
                f"bu saatlerde tepe {_hiz(tepe)} · gün ortalaması {_hiz(genel)} "
                f"({tepe / genel:.1f} katı)"
            ),
        })
    return bulgular


def _ara_ara_kopma(conn, since: int, now: int, gun_sayisi: int) -> list[dict]:
    """Sürekli değil, günlere yayılmış kopmalar.

    Tek seferlik uzun bir kesinti arıza kaydına düşer ve orada görünür. Buradaki
    asıl değer, tek tek bakınca önemsiz görünen ama aylardır tekrarlayan kısa
    kopmaları toplu hâlde göstermek.
    """
    if gun_sayisi < 5:
        return []
    rows = conn.execute(
        "SELECT hostid, name, region,"
        "       COUNT(DISTINCT date(ts,'unixepoch','localtime')) AS kopuk_gun,"
        "       SUM(CASE WHEN reachable = 0 THEN 1 ELSE 0 END) AS kopuk_olcum"
        " FROM measurements"
        " WHERE ts > ? AND planned = 0 AND reachable = 0"
        " GROUP BY hostid HAVING kopuk_gun >= 3",
        (since,),
    ).fetchall()

    bulgular = []
    for r in rows:
        toplam = conn.execute(
            "SELECT COUNT(*) n FROM measurements WHERE hostid = ? AND ts > ? AND planned = 0",
            (r["hostid"], since),
        ).fetchone()["n"] or 1
        oran = r["kopuk_olcum"] / toplam * 100
        # %20'yi geçiyorsa bu "ara ara" değil, süregelen bir kesintidir; onu
        # arıza kaydı bölümü zaten gösteriyor.
        if oran > 20:
            continue
        bulgular.append({
            "kimlik": f"kopma:{r['hostid']}",
            "hostid": r["hostid"], "ad": r["name"], "bolge": r["region"],
            "tur": "kopma",
            "vade": "uzun" if r["kopuk_gun"] >= 7 else "kisa",
            "baslik": f"{gun_sayisi} günün {r['kopuk_gun']} gününde ara ara ping kopması",
            "ayrinti": (
                "Kopmalar kısa ve dağınık, tek tek bakınca gözden kaçıyor. "
                "Bu dağılım genellikle hat kalitesi, güç sorunu ya da arızalı "
                "SFP/kablo işaretidir."
            ),
            "kanit": f"{r['kopuk_olcum']} başarısız ölçüm · tüm ölçümlerin %{oran:.2f}'i",
        })
    return bulgular


def _doluluk(conn, since: int, gun_sayisi: int, esik: float) -> list[dict]:
    """Hat kapasitesinin günlerce zorlanması."""
    if gun_sayisi < 4:
        return []
    rows = conn.execute(
        "SELECT hostid, name, region, date(ts,'unixepoch','localtime') AS gun,"
        "       MAX(util_pct) AS tepe"
        " FROM measurements WHERE ts > ? AND planned = 0 AND util_pct IS NOT NULL"
        " GROUP BY hostid, gun ORDER BY hostid, gun",
        (since,),
    ).fetchall()

    gunluk: dict[str, dict[str, Any]] = {}
    for r in rows:
        g = gunluk.setdefault(r["hostid"], {"ad": r["name"], "bolge": r["region"], "gunler": []})
        g["gunler"].append((r["gun"], r["tepe"]))

    bulgular = []
    for hostid, g in gunluk.items():
        dolu = [gun for gun, tepe in g["gunler"] if tepe >= esik]
        if len(dolu) < 3:
            continue
        tepe = max(t for _, t in g["gunler"])
        # %100'ü aşan doluluk, kapasitenin geçmiş trafikten TAHMİN edildiğini ve
        # tahminin düşük kaldığını gösterir. Rakamı olduğu gibi yazıp sebebini
        # söylemek, sessizce 100'e kırpmaktan dürüst.
        tahmin_notu = (
            " Oran %100'ü aşıyor: hat kapasitesi geçmiş trafikten tahmin ediliyor "
            "ve tahmin gerçek abonelik hızının altında kalmış. Gerçek hız "
            "config.yaml'daki bandwidth.per_host alanına girilirse oran kesinleşir."
            if tepe > 100 else ""
        )
        bulgular.append({
            "kimlik": f"doluluk:{hostid}",
            "hostid": hostid, "ad": g["ad"], "bolge": g["bolge"],
            "tur": "doluluk",
            "vade": "uzun" if len(dolu) >= 7 else "kisa",
            "baslik": f"{len(dolu)} gündür hat kapasitesi zorlanıyor",
            "ayrinti": (
                "Hat, günün bir bölümünde kapasitesinin sınırına dayanıyor. "
                "Bu bir arıza değil, kapasite yetersizliğidir — yavaşlık "
                "şikâyetlerinin en sık sebebi." + tahmin_notu
            ),
            "kanit": f"tepe doluluk %{tepe:.0f} · eşik %{esik:.0f} · {len(dolu)} gün aşıldı",
        })
    return bulgular


def _hiz(bps: float) -> str:
    from .render import fmt_bps
    return fmt_bps(bps)


def calistir(store, config: dict[str, Any], now: int | None = None) -> dict[str, Any]:
    """Tüm analizleri çalıştırır. Dönen: {'gun': N, 'bulgular': [...]}"""
    global _onbellek
    now = now or int(time.time())
    if _onbellek and (now - _onbellek[0]) < ONBELLEK_SN:
        return _onbellek[1]

    since = now - PENCERE_GUN * 86400
    th = config["thresholds"]
    try:
        with store._conn() as conn:
            gun = _gun_sayisi(conn, since)
            bulgular = (
                _yavaslik(conn, since, now, float(th.get("latency_warn_ms", 80)))
                + _doluluk(conn, since, gun, float(th.get("bandwidth_util_warn", 75)))
                + _ara_ara_kopma(conn, since, now, gun)
                + _saat_yogunlugu(conn, since, gun)
            )
    except Exception:
        log.exception("Analiz üretilemedi")
        return {"gun": 0, "bulgular": [], "hata": True}

    # Uzun vadeli bulgular önce: kısa süreli bir dalgalanma, aylardır süren bir
    # sorunun üstüne çıkmamalı.
    sira = {"uzun": 0, "kisa": 1}
    bulgular.sort(key=lambda b: (sira.get(b["vade"], 2), b["ad"] or ""))
    sonuc = {"gun": gun, "bulgular": bulgular}
    _onbellek = (now, sonuc)
    return sonuc
