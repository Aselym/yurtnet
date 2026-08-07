"""Yönetici ve teknik rapor sayfaları.

İki farklı okuyucu için iki farklı sayfa:

- **Yönetici raporu**: "durum iyi mi, nerede sorun var, ne yapmalıyım" sorularını
  bir bakışta cevaplar. Az yazı, çok grafik, teknik terim yok.
- **Teknik servis raporu**: müdahale edecek kişi için tam döküm — her arıza
  kaydının başlangıcı, bitişi, sıklığı, sebebi, hangi Zabbix ölçümünden ve
  hangi eşikten çıktığı, o andaki hat değerleri; ayrıca yurt bazlı ölçümler
  ve izleme altyapısının kendi sağlığı.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from . import pages, regions
from .render import esc, fmt_bps, fmt_duration, fmt_ms, fmt_pct, fmt_time
from .report import CODE_LABEL
from .store import KESINTI_KODLARI, Store, ariza_suresi

GUN_KISA = {0: "Pzt", 1: "Sal", 2: "Çar", 3: "Per", 4: "Cum", 5: "Cmt", 6: "Paz"}

# Bunlar yurdun internet sorunu değil, izleme kurulumumuzun eksiği. Yönetici
# raporunun grafiklerine karışırsa "en büyük sorununuz şu" gibi görünür ve
# interneti gayet çalışan yurtları "sürekli sorun çıkarıyor" diye işaretler.
# Ayrı bir satırda dürüstçe belirtilir, ama sorun sayımına katılmaz.
IZLEME_KODLARI = {"NO_IF_DATA", "STALE_DATA"}

# Her ön tanı kodunun arkasındaki ölçüm: hangi Zabbix item'ından geldiği, neye
# bakıldığı, hangi eşiğin aşıldığı ve kararı veren kural. Teknik servis
# raporundaki "bilginin kaynağı" sütunu buradan doluyor — servis ekibi bir
# kaydı tartışırken diagnose.py'yi açmak zorunda kalmasın.
VERI_KAYNAGI: dict[str, dict[str, Any]] = {
    "HOST_DOWN": {
        "item": "icmpping",
        "olcut": "ICMP ping cevabı",
        "esik": lambda th: "cevap yok (0)",
        "kural": "_rule_down",
    },
    "NO_DATA": {
        "item": "— (tüm item'lar sessiz)",
        "olcut": "Kontrol penceresinde hiç ölçüm gelmemesi",
        "esik": lambda th: "veri yok",
        "kural": "_rule_no_data",
    },
    "WAN_SILENT": {
        "item": "net.if.in[...], net.if.out[...]",
        "olcut": "WAN arayüzündeki toplam trafik (ping cevap verirken)",
        "esik": lambda th: "in+out ≤ 8 kbps (~1 KB/sn)",
        "kural": "_rule_wan_silent",
    },
    "WAN_IFACE_DOWN": {
        "item": "net.if.status[...]",
        "olcut": "WAN arayüzünün operasyonel durumu",
        "esik": lambda th: "durum = down",
        "kural": "_rule_wan_down",
    },
    "PACKET_LOSS": {
        "item": "icmppingloss",
        "olcut": "Ping paket kaybı yüzdesi",
        "esik": lambda th: f"uyarı ≥ %{th['loss_warn']:g} · kritik ≥ %{th['loss_crit']:g}",
        "kural": "_rule_packet_loss",
    },
    "HIGH_LATENCY": {
        "item": "icmppingsec",
        "olcut": "Ping yanıt süresi",
        "esik": lambda th: (
            f"uyarı ≥ {th['latency_warn_ms']:g} ms · kritik ≥ {th['latency_crit_ms']:g} ms"
        ),
        "kural": "_rule_latency",
    },
    "SATURATION": {
        "item": "net.if.in[...], net.if.out[...] + hat kapasitesi",
        "olcut": "Anlık trafiğin hat kapasitesine oranı",
        "esik": lambda th: (
            f"uyarı ≥ %{th['bandwidth_util_warn']:g} · kritik ≥ %{th['bandwidth_util_crit']:g}"
        ),
        "kural": "_rule_saturation",
    },
    "REBOOTED": {
        "item": "system.net.uptime / system.hw.uptime",
        "olcut": "Cihazın çalışma süresi sayacı",
        "esik": lambda th: f"uptime ≤ {th['reboot_recent_minutes']:g} dk",
        "kural": "_rule_reboot",
    },
    "IF_ERRORS": {
        "item": "net.if.in.errors, net.if.out.errors, .discards",
        "olcut": "Hata/discard sayacındaki ARTIŞ (mutlak değer değil)",
        "esik": lambda th: f"iki ölçüm arasında ≥ {th['if_error_artis_esigi']:g} paket",
        "kural": "_rule_if_errors",
    },
    "HIGH_CPU": {
        "item": "system.cpu.util",
        "olcut": "Firewall işlemci kullanımı",
        "esik": lambda th: f"uyarı ≥ %{th['cpu_warn']:g} · kritik ≥ %{th['cpu_crit']:g}",
        "kural": "_rule_cpu",
    },
    "HIGH_MEMORY": {
        "item": "vm.memory.util",
        "olcut": "Firewall bellek kullanımı",
        "esik": lambda th: f"uyarı ≥ %{th['mem_warn']:g} · kritik ≥ %{th['mem_crit']:g}",
        "kural": "_rule_memory",
    },
    "FLAPPING": {
        "item": "icmpping (geçmiş ölçümler)",
        "olcut": "Son 1 saatte açık↔kapalı geçiş sayısı",
        "esik": lambda th: f"≥ {th['flap_count_1h']:g} geçiş / saat",
        "kural": "_rule_flapping",
    },
    "REGIONAL_OUTAGE": {
        "item": "icmpping (bölgedeki tüm yurtlar)",
        "olcut": "Aynı bölgede eşzamanlı erişilemeyen yurt sayısı",
        "esik": lambda th: f"≥ {th['regional_outage_min_hosts']:g} yurt aynı anda kopuk",
        "kural": "_regional_rules",
    },
    "STALE_DATA": {
        "item": "— (item'ların son güncellenme zamanı)",
        "olcut": "En son ölçümün üzerinden geçen süre",
        "esik": lambda th: f"≥ {th['stale_data_minutes']:g} dk güncellenmemiş",
        "kural": "_rule_stale",
    },
    "NO_IF_DATA": {
        "item": "net.if.* (SNMP arayüz keşfi)",
        "olcut": "Ping çalışırken arayüz verisinin hiç gelmemesi",
        "esik": lambda th: "arayüz item'ı yok",
        "kural": "_rule_no_interface_data",
    },
    "PLANNED_DOWN": {
        "item": "— (elle işaretleme)",
        "olcut": "Panodan 'bilinçli kapalı' işareti konmuş olması",
        "esik": lambda th: "arıza değil, bilgi",
        "kural": "_rule_planned",
    },
}

# Arıza kodlarının yöneticiye anlamlı gelen karşılıkları: teknik sebep yerine
# "ne oldu" dili.
YONETICI_DILI = {
    "NO_DATA": "Cihaza ulaşılamadı",
    "HOST_DOWN": "İnternet kesintisi",
    "WAN_IFACE_DOWN": "Hat kopukluğu",
    "WAN_SILENT": "İnternet kesintisi",
    "PACKET_LOSS": "Bağlantı kalitesi düşük",
    "HIGH_LATENCY": "Yavaşlık",
    "SATURATION": "Kapasite yetersiz",
    "IF_ERRORS": "Donanım/kablo sorunu",
    "REBOOTED": "Cihaz yeniden başladı",
    "FLAPPING": "Bağlantı sürekli kopuyor",
    "REGIONAL_OUTAGE": "Bölgesel kesinti",
    "STALE_DATA": "İzleme aksaması",
    "NO_IF_DATA": "İzleme eksiği",
    "HIGH_CPU": "Cihaz aşırı yüklendi",
    "HIGH_MEMORY": "Cihaz aşırı yüklendi",
}


def _hafta(store: Store, config: dict[str, Any], now: int) -> dict[str, Any]:
    since = now - 7 * 86400
    veri = store.weekly_stats(since, now)
    veri["gunler"] = store.daily_summary(since, now)
    veri["now"] = now
    return veri


def genel_durum(sinif: dict) -> tuple[str, str]:
    """Sayfanın üstündeki tek cümlelik durum.

    Uydurma bir yüzde eşiğine ("hedef") göre değil, o an gerçekten ne olduğuna
    bakar: müdahale bekleyen bir şey var mı, izlenmesi gereken bir şey var mı.
    Okuyanın alacağı aksiyon zaten bu ayrımdan çıkıyor.
    """
    if any(i.severity == "critical" for i in sinif["acik"]):
        return "kritik", "Müdahale bekleyen sorun var"
    if sinif["acik"]:
        return "uyari", "Devam eden sorun var"
    if sinif["tekrarlayan"]:
        return "uyari", "İzlenmesi gereken yurt var"
    return "iyi", "Ağ sağlıklı"


def siniflandir(incidents: list, now: int, onemli_sn: int, tekrar_esigi: int) -> dict:
    """Olayları "müdahale gerektiren" ve "kendiliğinden geçmiş gürültü" diye ayırır.

    Yöneticiye "12 yurtta sorun var" demek, o sorunların 11'i beş dakikada
    kendiliğinden düzeldiyse yanıltıcıdır — panik yaratır, gerçek sorunu gizler.
    Yönetici seviyesinde bir sorun ancak şu üç durumda gerçektir:

      1. Hâlâ sürüyor (açık),
      2. Kısa sürmedi (eşiğin üzerinde bir süre devam etti),
      3. Kısa ama tekrar tekrar oluyor — asıl erken uyarı sinyali budur;
         kullanıcı henüz aramamıştır ama hat bozulmaya başlamıştır.
    """
    acik = [i for i in incidents if i.ended_at is None]
    uzun = [
        i for i in incidents
        if i.ended_at is not None and (i.ended_at - i.started_at) >= onemli_sn
    ]
    kisa = [
        i for i in incidents
        if i.ended_at is not None and (i.ended_at - i.started_at) < onemli_sn
    ]

    # Tekrar sayımı yurt+sorun tipi bazında: aynı yurtta aynı şeyin
    # tekrarlaması, farklı şeylerin bir kez olmasından çok daha anlamlı.
    sayac: dict[tuple[str, str], list] = {}
    for i in kisa:
        if i.hostid:
            sayac.setdefault((i.hostid, i.code), []).append(i)
    tekrarlayan = {k: v for k, v in sayac.items() if len(v) >= tekrar_esigi}

    tekrar_hostlari = {h for h, _ in tekrarlayan}
    onemsiz = [
        i for i in kisa
        if not i.hostid or (i.hostid, i.code) not in tekrarlayan
    ]

    dikkat_hostlari = (
        {i.hostid for i in acik if i.hostid}
        | {i.hostid for i in uzun if i.hostid}
        | tekrar_hostlari
    )
    return {
        "acik": acik,
        "uzun": uzun,
        "tekrarlayan": tekrarlayan,
        "onemsiz": onemsiz,
        "dikkat_hostlari": dikkat_hostlari,
    }


def sorunlu_zaman(
    incidents: list, hosts: list[dict], now: int
) -> dict[str, dict[str, Any]]:
    """Her yurdun izlenen süresinin ne kadarında sorunlu olduğunu hesaplar.

    Çıplak olay sayısı ("18 kez") karşılaştırılabilir değildir: iki gündür
    izlenen yurtla iki aydır izlenen yurdun 18'i aynı şeyi ifade etmez.
    Anlamlı olan orandır — yurdun izlendiği sürenin yüzde kaçında sorunluydu.

    Payda olarak ölçüm sayısı değil gerçek zaman aralığı kullanılır; kontrol
    aralığı (5 dk -> 1 dk) zaman içinde değiştiği için ölçüm sayısı yanıltır.
    """
    sure: dict[str, int] = {}
    adet: dict[str, int] = {}
    son: dict[str, int] = {}
    acik: set[str] = set()
    for i in incidents:
        if not i.hostid:
            continue
        sure[i.hostid] = sure.get(i.hostid, 0) + ariza_suresi(i, now)
        adet[i.hostid] = adet.get(i.hostid, 0) + 1
        bitis = i.ended_at or now
        son[i.hostid] = max(son.get(i.hostid, 0), bitis)
        if i.ended_at is None:
            acik.add(i.hostid)

    sonuc: dict[str, dict[str, Any]] = {}
    for h in hosts:
        gozlem = h.get("gozlem_sn") or 0
        s = sure.get(h["hostid"], 0)
        sonuc[h["hostid"]] = {
            "sure": s,
            "adet": adet.get(h["hostid"], 0),
            "gozlem": gozlem,
            "oran": (s / gozlem * 100) if gozlem > 0 else None,
            # Son olayın ne kadar önce bittiği aciliyeti belirler: yarım gündür
            # sesi çıkmayan bir yurt, hâlâ sorunlu olanla aynı şey değildir.
            "son": son.get(h["hostid"]),
            "acik": h["hostid"] in acik,
        }
    return sonuc


def _oran_hucresi(bilgi: dict, en_yuksek: float) -> str:
    """Oran + çubuk. Payda her zaman yazılır ki sayı bağlamsız kalmasın."""
    oran = bilgi.get("oran")
    if oran is None:
        return '<td class="sonuk">ölçülemedi</td>'
    dolu = max(3.0, (oran / en_yuksek * 100) if en_yuksek > 0 else 3.0)
    return (
        f'<td><div class="olcu"><div class="yol"><div class="dolu" '
        f'style="width:{dolu:.1f}%"></div></div>'
        f'<span class="sayi" style="font-weight:600;min-width:46px">%{oran:.2f}</span></div>'
        f'<div class="sonuk" style="font-size:11px;margin-top:3px">'
        f'{esc(fmt_duration(bilgi["sure"]))} / {esc(fmt_duration(bilgi["gozlem"]))} izlenen süre'
        f"</div></td>"
    )


# Yönetici raporundaki her sorun kaynağının karşılığı: ne olduğu ve ne
# yapılması gerektiği. Grafikte "Yavaşlık: 17" yazması tek başına ne olduğunu
# anlatmıyor; okuyanın yanında sözlüğü olmalı.
KAYNAK_ACIKLAMA: dict[str, tuple[str, str]] = {
    "İnternet kesintisi": (
        "İnternet tamamen kesildi. Cihaz kapalı, elektrik yok ya da hat kopuk.",
        "ISP'ye kesinti kaydı açılır; çözülmezse sahaya çıkılır.",
    ),
    "Yavaşlık": (
        "Bağlantı çalışıyor ama gecikme yüksek. Görüntülü görüşme donar, "
        "sayfalar geç açılır.",
        "Hat doluluğu ve ISP yönlendirmesi kontrol edilir.",
    ),
    "Donanım/kablo sorunu": (
        "Cihazın arayüzünde yeni hatalı paketler oluşuyor. Kablo, SFP modül "
        "veya port kaynaklı olur.",
        "Kablo/SFP değişimi planlanır, port ayarları teyit edilir.",
    ),
    "Kapasite yetersiz": (
        "Hat dolmuş. Bu bir arıza değil, hattın ihtiyacı karşılamaması.",
        "Kota/QoS uygulanır ya da hat kapasitesi artırılır.",
    ),
    "Bağlantı kalitesi düşük": (
        "Paketlerin bir kısmı kayboluyor. Kullanıcı 'kopuyor' der ama bağlantı "
        "aslında kopmuyor.",
        "ISP'ye hat kalitesi kaydı açılır.",
    ),
    "Cihaz yeniden başladı": (
        "Firewall yeniden başlamış. Elektrik kesintisi, güç sorunu veya "
        "kilitlenme olabilir.",
        "Tekrarlıyorsa UPS ve cihaz donanımı kontrol ettirilir.",
    ),
    "Bağlantı sürekli kopuyor": (
        "Hat kısa aralıklarla defalarca inip kalkıyor. Tek seferlik kesintiden "
        "daha ciddidir.",
        "Yerinde müdahale gerekir; ISP'ye flapping kaydı açılır.",
    ),
    "Hat kopukluğu": (
        "İnternet bacağı fiziksel olarak kapalı. Kablo çıkmış ya da ISP portu "
        "kapanmış olabilir.",
        "Kablo/SFP kontrolü; sağlamsa ISP'ye port kaydı açılır.",
    ),
    "Cihaza ulaşılamadı": (
        "Cihazdan hiçbir veri gelmiyor. Kapalı ya da tamamen erişilemez durumda.",
        "Yurtla iletişime geçilip elektrik ve cihaz durumu teyit ettirilir.",
    ),
    "Bölgesel kesinti": (
        "Aynı bölgede birden fazla yurt aynı anda etkilendi. Tek tek arıza "
        "olma ihtimali düşük.",
        "Sahaya çıkmadan önce ISP'den bölgesel kesinti teyidi alınır.",
    ),
    "Cihaz aşırı yüklendi": (
        "Firewall'ın işlemci veya belleği dolmuş; hat boş olsa da trafiği "
        "işleyemiyor.",
        "Oturum sayısı ve tarama ayarları kontrol edilir.",
    ),
}


def _kaynak_sozlugu(tipler: dict[str, int]) -> str:
    """Grafikte görünen kaynakların ne anlama geldiğini açıklar.

    Yalnızca o dönemde gerçekten yaşanan kaynaklar listelenir; tüm kod
    listesini basmak sözlüğü referans metnine çevirir, kimse okumaz.
    """
    if not tipler:
        return '<p class="bos">Bu dönemde sorun yaşanmadı.</p>'
    satirlar = []
    for ad in sorted(tipler, key=lambda a: -tipler[a]):
        ne, yap = KAYNAK_ACIKLAMA.get(ad, ("—", "—"))
        satirlar.append(
            f"""<tr>
  <td style="width:24%"><strong>{esc(ad)}</strong></td>
  <td style="line-height:1.55">{esc(ne)}</td>
  <td style="line-height:1.55;color:var(--ink2)">{esc(yap)}</td>
</tr>"""
        )
    return (
        '<div class="sar"><table><tr><th>Kaynak</th><th>Ne anlama geliyor</th>'
        "<th>Ne yapılmalı</th></tr>" + "".join(satirlar) + "</table></div>"
    )


def _dakika_yaz(dakika: float) -> str:
    """Grafik etiketi için dakikayı okunabilir süreye çevirir: 176 -> '2 sa 56 dk'."""
    return fmt_duration(int(dakika) * 60)


def _hafta_etiketi(bitis_ts: int) -> str:
    """Haftayı bitiş tarihiyle etiketler: '5 Ağu'."""
    aylar = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
             "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    d = dt.datetime.fromtimestamp(bitis_ts)
    return f"{d.day} {aylar[d.month - 1]}"


def _gun_etiketi(gun_str: str) -> str:
    try:
        d = dt.date.fromisoformat(gun_str)
        return f"{GUN_KISA[d.weekday()]} {d.day}"
    except Exception:
        return gun_str


# ============================================================ YÖNETİCİ RAPORU


def yonetici(store: Store, config: dict[str, Any], logo: str, now: int | None = None) -> str:
    now = now or int(time.time())
    v = _hafta(store, config, now)
    hosts, gunler = v["hosts"], v["gunler"]

    # İzleme eksikleri yurdun sorunu değil; yönetici görünümünden ayrılır.
    incidents = [i for i in v["incidents"] if i.code not in IZLEME_KODLARI]
    izleme_eksigi = sorted(
        {i.name for i in v["incidents"] if i.code in IZLEME_KODLARI and i.name}
    )

    uptime = sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    kesinti = sum(
        ariza_suresi(i, now) for i in incidents if i.code in KESINTI_KODLARI
    )
    # Olaylar önemine göre ayrılır: kendiliğinden geçmiş kısa dalgalanmalar
    # yöneticiyi ilgilendirmez, süren ve tekrarlayanlar ilgilendirir.
    sinif = siniflandir(
        incidents,
        now,
        int(config["report"].get("onemli_sure_dakika", 10)) * 60,
        int(config["report"].get("tekrar_esigi", 4)),
    )
    acik = sinif["acik"]
    sorunlu = [h for h in hosts if h["hostid"] in sinif["dikkat_hostlari"]]

    # Karşılaştırma için önceki haftanın rakamları ve 8 haftalık eğilim serisi.
    seri = store.haftalik_seri(8, now)
    gecen_hafta = seri[-2] if len(seri) >= 2 and seri[-2]["veri_var"] else None
    durum, durum_yazi = genel_durum(sinif)

    planli = [h for h in hosts if h.get("planned_checks")]

    # Listeyi ikiye ayır: şu an sorunu olanla, şu an çalışan ama tekrar eden.
    # Tek liste hâlinde gösterilince "Florya neden burada, şu an bozuk mu?"
    # sorusu doğuyor — kart kendi kendini açıklamıyor.
    acik_hostlar = {i.hostid for i in sinif["acik"] if i.hostid}
    simdi_sorunlu = [
        _kisa_ad(h["name"]) for h in sorunlu if h["hostid"] in acik_hostlar
    ]
    izlenmesi_gereken = [
        _kisa_ad(h["name"]) for h in sorunlu if h["hostid"] not in acik_hostlar
    ]

    kesinti_notu = (
        "34 yurdun kesinti sürelerinin toplamı. İki yurt aynı anda bir saat "
        "kapalı kalırsa 2 saat sayılır."
    )
    # Liste kısaltılmıyor: "ve 2 yurt daha" demek, tam da öğrenilmek istenen
    # bilgiyi saklıyor. Rozetler satır sonunda alta kaydığı için uzun liste de
    # düzeni bozmuyor.
    bolumler = []
    if simdi_sorunlu:
        bolumler.append(
            '<div style="font-size:11px;color:var(--kritik-ink);font-weight:700;'
            'text-transform:uppercase;letter-spacing:.04em;margin-top:9px">Şu an sorunlu</div>'
            + pages.yurt_rozetleri(simdi_sorunlu, "kritik")
        )
    if izlenmesi_gereken:
        bolumler.append(
            '<div style="font-size:11px;color:var(--uyari-ink);font-weight:700;'
            'text-transform:uppercase;letter-spacing:.04em;margin-top:12px">'
            "Şu an çalışıyor, tekrar ettiği için izlemede</div>"
            + pages.yurt_rozetleri(izlenmesi_gereken, "uyari")
        )
    sorunlu_notu = "".join(bolumler) or "Tüm yurtlar sorunsuz çalıştı."

    govde = [
        "<h1>Yönetici Raporu</h1>",
        f'<p class="alt">{esc(fmt_time(v["since"]))} – {esc(fmt_time(now))} · '
        f'{len(hosts)} yurt izlendi · {pages.rozet(durum, durum_yazi)}'
        + (
            f' · {len(planli)} yurt bilinçli kapalı (hesaba katılmadı)'
            if planli
            else ""
        )
        # Aylık bölüm sayfanın en altında; uzun sayfada gözden kaçmasın diye
        # üstten doğrudan bir bağlantı verilir.
        + ' · <a href="#aylik" style="color:var(--seri);text-decoration:none;'
        'font-weight:600">Aylık görünüme git ↓</a>'
        + "</p>",
        pages.kpi(
            [
                (
                    # İki basamak: 33 yurt %100, biri %99.6 iken "%100.0" yazmak,
                    # hemen altında sorunlu yurt listelenirken çelişkili duruyor.
                    fmt_pct(uptime, 2),
                    "Başarılı çalışma oranı",
                    "Yurtların internetinin çalışır durumda olduğu zamanın oranı."
                    + pages.delta(
                        uptime,
                        gecen_hafta["uptime_pct"] if gecen_hafta else None,
                        yuksek_iyi=True,
                        bicim=lambda d: f"%{d:.2f}",
                        esik=0.01,
                    ),
                ),
                (
                    fmt_duration(kesinti),
                    "Toplam kesinti",
                    kesinti_notu
                    + pages.delta(
                        kesinti,
                        gecen_hafta["kesinti_sn"] if gecen_hafta else None,
                        bicim=fmt_duration,
                        esik=59,
                    ),
                ),
                (
                    f"{len(sorunlu)} / {len(hosts)}",
                    "Dikkat gereken yurt",
                    sorunlu_notu
                    + pages.delta(
                        len(sorunlu),
                        gecen_hafta["etkilenen_yurt"] if gecen_hafta else None,
                        bicim=lambda d: f"{d:.0f} yurt",
                    ),
                ),
                (
                    f"{len(acik)}",
                    "Şu anda süren sorun",
                    (
                        "Devam eden ve henüz çözülmemiş sorunlar. Müdahale gereken "
                        "sayı budur."
                        if acik
                        else "Şu anda devam eden bir sorun yok, ağ çalışır durumda."
                    ),
                ),
            ],
            one_cikar=True,
        ),
    ]

    # Sayfanın en üstünde ne yapılması gerektiği yazar; grafikler sonra gelir.
    zaman = sorunlu_zaman(incidents, hosts, now)
    govde.append(_su_an_karti(sinif, now))
    govde.append(
        '<div class="izgara">'
        + _dagilim_karti(store, hosts)
        + _gecikme_karti(hosts)
        + "</div>"
    )
    # "En çok sorun yaşayan yurtlar" buraya, üst sıraya taşındı: erken uyarı
    # tablosuyla birleşti. Durum sütunu "izlemede"yi, yeni "Son olay" sütunu
    # aciliyeti taşıyor — ayrı bir tablo tutmaya gerek kalmadı.
    govde.append(
        pages.kart(
            "En çok sorun yaşayan yurtlar",
            _yonetici_tablo(sorunlu, zaman, now, sinif, _yurt_sorun_tipleri(incidents)),
            aciklama=(
                "Sıralama olay sayısına değil, yurdun izlendiği sürenin ne kadarında "
                "sorunlu olduğuna göre yapılır. \"İzlemede\" olanlarda şu anda bir sorun "
                "yok; tekrar ettikleri için listede — şikâyet gelmeden kontrol edilmeli."
            ),
        )
    )

    # Eğilim: tek bir kötü hafta mı, yoksa aylardır kötüye mi gidiyor?
    # Bu ikisi çok farklı kararlar gerektirir.
    govde.append(
        pages.kart(
            "Son 8 haftanın eğilimi",
            pages.egilim_grafik(
                [(_hafta_etiketi(h["bitis"]), (h["olay"] if h["veri_var"] else None)) for h in seri]
            ),
            aciklama=(
                "Haftalık toplam olay sayısı. Tek bir kötü hafta ile aylardır süren "
                "bir bozulma farklı şeylerdir; bu grafik ikisini ayırt etmenizi sağlar."
            ),
        )
    )

    # Kesinti süresi güne göre — sıfırdan başlayan, farkı gerçekten gösteren ölçü.
    gunluk = [
        (_gun_etiketi(g["gun"]), round((g["kesinti_sure"] or 0) / 60)) for g in gunler
    ]
    govde.append(
        pages.kart(
            "Günlük kesinti süresi",
            pages.sutun_grafik(gunluk, bicim=_dakika_yaz)
            if any(d for _, d in gunluk)
            else '<p class="bos">Bu hafta hiç kesinti yaşanmadı.</p>',
            aciklama=(
                "Her gün, tüm yurtlarda toplam ne kadar internet kesintisi yaşandığı. "
                "Aynı anda iki yurt yarım saat kapalı kalırsa o gün 1 saat sayılır."
            ),
        )
    )

    # Bölge dağılımı grafiği kaldırıldı: yer kaplıyordu, karşılığında bir karar
    # üretmiyordu. Bölgesel yoğunlaşma varsa "Öne çıkanlar"da tek cümleyle söylenir.
    bolge_sayim: dict[str, int] = {}
    for i in incidents:
        ad = i.region or "—"
        bolge_sayim[ad] = bolge_sayim.get(ad, 0) + 1
    bolge = sorted(bolge_sayim.items(), key=lambda x: -x[1])[:8]

    # "Sorunlar ne kaynaklı" ve kaynak sözlüğü teknik rapora taşındı: yöneticinin
    # sorusu "hangi yurda müdahale edeyim", sebep kırılımı müdahale edenin işi.

    govde.append(
        pages.kart(
            "Öne çıkanlar",
            _dikkat_cekenler(
                incidents, bolge, sorunlu, izleme_eksigi, seri, sinif
            ),
            aciklama="Bu haftanın sayılara bakınca gözden kaçabilecek noktaları.",
        )
    )
    govde.append('<div id="aylik"></div>')
    govde.append(_aylik_bolum(store, config, now))

    return pages.shell(
        baslik="Yönetici Raporu — Yurt İnterneti",
        aktif="/yonetici",
        govde="\n".join(govde),
        logo=logo,
    )


def _su_an_karti(sinif: dict, now: int) -> str:
    """Sayfanın en üstündeki soru: şu anda müdahale gereken bir şey var mı?"""
    acik, uzun = sinif["acik"], sinif["uzun"]
    if not acik:
        icerik = (
            '<p style="font-size:14px;margin:0;color:var(--iyi-ink);font-weight:600">'
            "✓ Şu anda devam eden bir sorun yok.</p>"
            '<p style="font-size:13px;color:var(--ink2);margin:9px 0 0;line-height:1.6">'
            + (
                f"Bu hafta {len(uzun)} sorun yaşandı ancak hepsi çözüldü."
                if uzun
                else "Bu hafta müdahale gerektiren bir sorun yaşanmadı."
            )
            + "</p>"
        )
        return pages.kart("Şu anki durum", icerik, aciklama="Müdahale bekleyen sorunlar.")

    satirlar = []
    for i in sorted(acik, key=lambda x: x.started_at):
        sure = now - i.started_at
        satirlar.append(
            f"""<tr>
  <td><strong>{esc(_kisa_ad(i.name) if i.name else (i.region or '—'))}</strong></td>
  <td>{esc(YONETICI_DILI.get(i.code, i.code))}</td>
  <td class="sayi">{esc(fmt_duration(sure))}</td>
  <td class="sayi sonuk">{esc(fmt_time(i.started_at))}</td>
  <td>{'Uzaktan çözülebilir' if i.remote_fixable else 'Yerinde müdahale'}</td>
</tr>"""
        )
    return pages.kart(
        "Şu anki durum",
        f'<p style="font-size:14px;margin:0 0 14px;color:var(--kritik-ink);font-weight:600">'
        f"{len(acik)} sorun devam ediyor ve müdahale bekliyor.</p>"
        '<div class="sar"><table><tr><th>Yurt</th><th>Sorun</th><th>Süredir</th>'
        "<th>Başlangıç</th><th>Müdahale</th></tr>" + "".join(satirlar) + "</table></div>",
        aciklama="Müdahale bekleyen sorunlar.",
    )


def _dagilim_karti(store: Store, hosts: list[dict]) -> str:
    """Tüm yurtların ŞU ANKİ durum dağılımı.

    Haftalık toplamlar değil, bu an: bir yurdun açık kaydı varsa onun en ağır
    seviyesi neyse o. Bilgi seviyesindeki bulgular (izleme eksiği, bilinçli
    kapatma) yurdun internetini etkilemediği için normal sayılır.
    """
    acik = store.acik_incident_severity()
    kritik = sum(1 for h in hosts if acik.get(h["hostid"]) == "critical")
    uyari = sum(1 for h in hosts if acik.get(h["hostid"]) == "warning")
    normal = len(hosts) - kritik - uyari

    return pages.kart(
        "Yurtların şu anki durumu",
        pages.pasta_grafik(
            [
                ("Normal çalışıyor", normal, "var(--iyi)"),
                ("Uyarı", uyari, "var(--uyari)"),
                ("Kritik", kritik, "var(--kritik)"),
            ],
            baslik_ic="yurt",
        ),
        aciklama=(
            "Şu an itibarıyla tüm yurtların durumu. İzleme eksiği veya bilinçli "
            "kapatma gibi bilgi niteliğindeki durumlar, yurdun interneti çalıştığı "
            "için normal sayılır."
        ),
    )


def _gecikme_karti(hosts: list[dict]) -> str:
    """Bölgelere göre ortalama yanıt süresi — arıza değil, hizmet kalitesi.

    Bölgeler arası fark kusur değil coğrafyadır: İstanbul omurgaya yakın,
    Şanlıurfa uzak. Rakamın iyi mi kötü mü olduğu tartışmaya açık kalmasın
    diye altına ölçek notu konur.
    """
    toplam: dict[str, dict[str, float]] = {}
    for h in hosts:
        if not h.get("avg_latency"):
            continue
        agirlik = h.get("checks") or 1
        t = toplam.setdefault(h["region"], {"toplam": 0.0, "agirlik": 0.0, "yurt": 0})
        t["toplam"] += h["avg_latency"] * agirlik
        t["agirlik"] += agirlik
        t["yurt"] += 1

    if not toplam:
        return pages.kart(
            "Bölgelere göre yanıt süresi",
            '<p class="bos">Henüz yeterli ölçüm yok.</p>',
            aciklama="Yurtlara gidiş-dönüş süresi.",
        )

    veriler = sorted(
        (
            (f"{bolge} ({int(v['yurt'])} yurt)", round(v["toplam"] / v["agirlik"], 1))
            for bolge, v in toplam.items()
        ),
        key=lambda x: x[1],
    )
    en_iyi, en_kotu = veriler[0][1], veriler[-1][1]

    return pages.kart(
        "Bölgelere göre yanıt süresi",
        pages.yatay_grafik(veriler, birim=" ms")
        + f'<p class="ipucu">Kısa olması iyidir. Bu hafta {en_iyi:.0f}–{en_kotu:.0f} ms '
        "aralığında; genel kabul 30 ms altının iyi, 100 ms üstünün kullanıcı "
        "tarafından hissedilir olduğudur. Bölgeler arası fark büyük ölçüde "
        "omurgaya olan mesafeden kaynaklanır.</p>",
        aciklama=(
            "Yurtlara gidiş-dönüş süresi — bağlantının ne kadar hızlı yanıt verdiğini "
            "gösterir. Ölçüm ağırlıklı ortalamadır."
        ),
    )


def _aylik_bolum(store: Store, config: dict[str, Any], now: int) -> str:
    """Son 30 günün özeti.

    Haftalık görünüm "şu an ne oluyor" sorusunu cevaplar; aylık görünüm ise
    eğilimi gösterir — bir yurt her hafta biraz daha mı kötüleşiyor, yoksa
    tek seferlik bir olay mıydı. Veri henüz birikmediyse bölüm kaybolmaz;
    ne zaman dolacağını söyler.
    """
    since = now - 30 * 86400
    ilk = store.veri_baslangici()
    kapsam_gun = max(0, (now - ilk) // 86400) if ilk else 0

    if not ilk or kapsam_gun < 1:
        return pages.kart(
            "Aylık görünüm",
            '<p class="bos">Aylık rapor için henüz yeterli veri toplanmadı. '
            "İzleme çalıştıkça bu bölüm kendiliğinden dolmaya başlayacak.</p>",
            aciklama="Son 30 günün özeti ve eğilimi.",
        )

    v = store.weekly_stats(since, now)
    gunler = store.daily_summary(since, now)
    hosts = v["hosts"]
    incidents = [i for i in v["incidents"] if i.code not in IZLEME_KODLARI]

    uptime = sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    kesinti = sum(
        ariza_suresi(i, now) for i in incidents if i.code in KESINTI_KODLARI
    )
    # Haftalık bölümle aynı ölçüt: kendiliğinden geçmiş kısa dalgalanma
    # "sorunlu yurt" saydırmaz. İki bölümün farklı sayı göstermesi kafa karıştırır.
    sinif = siniflandir(
        incidents,
        now,
        int(config["report"].get("onemli_sure_dakika", 10)) * 60,
        int(config["report"].get("tekrar_esigi", 4)),
    )
    dikkat = sinif["dikkat_hostlari"]
    zaman = sorunlu_zaman(incidents, hosts, now)

    # Veri kapsamı dürüstçe söylenir: 2 günlük veriyle "aylık %99.9" demek,
    # okuyanı ayın tamamı ölçülmüş gibi düşündürür.
    if kapsam_gun < 30:
        kapsam = (
            f"Şu ana kadar <strong>{kapsam_gun} günlük</strong> veri birikti. "
            f"Tam aylık görünüm için {30 - kapsam_gun} gün daha gerekiyor; "
            "aşağıdaki rakamlar eldeki veriye dayanıyor."
        )
    else:
        kapsam = "Son 30 günün tamamı ölçüldü."

    icerik = [
        f'<p style="font-size:13px;color:var(--ink2);margin:0 0 16px;line-height:1.6">{kapsam}</p>',
        pages.kpi(
            [
                (fmt_pct(uptime, 2), "Başarılı çalışma oranı", "30 günlük ortalama"),
                (fmt_duration(kesinti), "Toplam kesinti", "tüm yurtlar toplamı"),
                (
                    f"{len(dikkat)} / {len(hosts)}",
                    "Dikkat gereken yurt",
                    "Sorunu süren, uzun süren veya tekrarlayan yurtlar. "
                    "Kendiliğinden geçen kısa dalgalanmalar sayılmaz.",
                ),
                (
                    f"{len(sinif['acik'])}",
                    "Şu anda süren sorun",
                    "Devam eden ve müdahale bekleyen sorun sayısı."
                    if sinif["acik"]
                    else "Şu anda devam eden bir sorun yok.",
                ),
            ]
        ),
    ]

    aylik_gunluk = [
        (_gun_etiketi_kisa(g["gun"]), round((g["kesinti_sure"] or 0) / 60)) for g in gunler
    ]
    if any(d for _, d in aylik_gunluk):
        icerik.append(
            '<h3 style="font-size:13px;font-weight:620;margin:8px 0 12px">'
            "Günlük kesinti süresi</h3>"
        )
        icerik.append(pages.sutun_grafik(aylik_gunluk, bicim=_dakika_yaz))
    else:
        icerik.append('<p class="bos">Bu dönemde kesinti yaşanmadı.</p>')

    # Sıralama çıplak sayıya değil orana göre: farklı sürelerde izlenen
    # yurtların olay sayıları doğrudan karşılaştırılamaz.
    dikkat_hostlari = [h for h in hosts if h["hostid"] in dikkat]
    sirali = sorted(
        dikkat_hostlari, key=lambda h: -(zaman.get(h["hostid"], {}).get("oran") or 0)
    )[:6]
    if sirali:
        icerik.append(
            '<h3 style="font-size:13px;font-weight:620;margin:22px 0 4px">'
            "Ay boyunca en çok sorun yaşayan yurtlar</h3>"
            '<p class="kart-ac" style="margin:0 0 12px">İzlendiği sürenin yüzde kaçında '
            "sorunlu olduğuna göre sıralanır.</p>"
        )
        icerik.append(
            pages.yatay_grafik(
                [
                    (_kisa_ad(h["name"]), round(zaman.get(h["hostid"], {}).get("oran") or 0, 2))
                    for h in sirali
                ],
                onek="%",
            )
        )

    # Tek indirme: haftalık PDF kaldırıldı, aylık rapor iki sayfalık tam görünüm.
    icerik.append(
        '<div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--line);'
        'display:flex;gap:10px;flex-wrap:wrap">'
        '<a class="pdf-dugme" href="/pdf/aylik">⭳ Aylık raporu indir (PDF)</a></div>'
    )
    return pages.kart(
        "Aylık görünüm", "".join(icerik), aciklama="Son 30 günün özeti ve eğilimi."
    )


def _gun_etiketi_kisa(gun_str: str) -> str:
    """Aylık grafikte gün adı sığmaz; sadece ayın günü yazılır."""
    try:
        d = dt.date.fromisoformat(gun_str)
        return str(d.day)
    except Exception:
        return gun_str


def _yurt_sorun_tipleri(incidents: list) -> dict[str, list[str]]:
    """hostid -> yaşadığı sorun tipleri, sık olandan aza doğru."""
    sayac: dict[str, dict[str, int]] = {}
    for i in incidents:
        if not i.hostid:
            continue
        ad = YONETICI_DILI.get(i.code, i.code)
        sayac.setdefault(i.hostid, {})
        sayac[i.hostid][ad] = sayac[i.hostid].get(ad, 0) + 1
    return {
        hostid: sorted(tipler, key=lambda a: -tipler[a])
        for hostid, tipler in sayac.items()
    }


def _yonetici_tablo(
    sorunlu: list[dict], zaman: dict, now: int, sinif: dict, tipler: dict[str, list[str]]
) -> str:
    if not sorunlu:
        return '<p class="bos">Bu hafta hiçbir yurtta kayda değer sorun yaşanmadı.</p>'

    sirali = sorted(
        sorunlu, key=lambda h: -(zaman.get(h["hostid"], {}).get("oran") or 0)
    )[:6]
    en_yuksek = max(
        ((zaman.get(h["hostid"], {}).get("oran") or 0) for h in sirali), default=1
    ) or 1

    # Durum sütunu "şu an ne olduğunu" söyler; geçmişteki şiddeti değil.
    # Okuyan kişi bu satıra bakıp bugün bir şey yapması gerekip gerekmediğini bilmeli.
    acik_hostlar = {i.hostid for i in sinif["acik"] if i.hostid}
    izlemedekiler = {h for h, _ in sinif["tekrarlayan"]}

    satirlar = []
    for h in sirali:
        b = zaman.get(h["hostid"], {})
        if h["hostid"] in acik_hostlar:
            d, y = "kritik", "Devam ediyor"
        elif h["hostid"] in izlemedekiler:
            d, y = "uyari", "İzlemede"
        else:
            d, y = "iyi", "Sorun çözüldü"
        sorunlar = tipler.get(h["hostid"], [])
        sorun_metni = (
            ", ".join(esc(s) for s in sorunlar[:3])
            + (f" <span class='sonuk'>+{len(sorunlar) - 3}</span>" if len(sorunlar) > 3 else "")
            if sorunlar
            else '<span class="sonuk">—</span>'
        )
        satirlar.append(
            f"""<tr>
  <td><strong>{esc(_kisa_ad(h['name']))}</strong></td>
  <td class="sonuk">{esc(h['region'])}</td>
  <td>{pages.rozet(d, y)}</td>
  <td style="line-height:1.5;max-width:210px">{sorun_metni}</td>
  {_oran_hucresi(b, en_yuksek)}
  <td>{_son_olay_hucresi(b, now)}</td>
  <td class="sayi" style="text-align:right"><strong>{esc(fmt_pct(h['uptime_pct'], 2))}</strong></td>
</tr>"""
        )
    return (
        '<div class="sar"><table><tr><th>Yurt</th><th>Bölge</th><th>Durum</th>'
        "<th>Yaşanan sorunlar</th><th>Sorunlu geçen zaman</th><th>Son olay</th>"
        '<th style="text-align:right">Başarılı çalışma oranı</th></tr>'
        + "".join(satirlar)
        + "</table></div>"
    )


def _son_olay_hucresi(bilgi: dict, now: int) -> str:
    """Son olayın ne kadar önce bittiği. Renk tazeliği vurgular, yazı hep var."""
    if bilgi.get("acik"):
        return pages.rozet("kritik", "Şu anda sürüyor")
    son = bilgi.get("son")
    if not son:
        return '<span class="sonuk">—</span>'
    gecen = now - son
    tazelik = "iyi" if gecen > 43200 else ("uyari" if gecen > 7200 else "kritik")
    return pages.rozet(tazelik, f"{fmt_duration(gecen)} önce")


def _dikkat_cekenler(
    incidents: list, bolge: list[tuple[str, int]], sorunlu: list,
    izleme_eksigi: list[str], seri: list[dict], sinif: dict,
) -> str:
    """Sayıların arkasındaki hikâyeyi birkaç cümleyle söyler."""
    maddeler: list[str] = []

    # Önce genel değerlendirme: rakam iyi mi kötü mü sorusunu okuyan yerine biz cevaplarız.
    veri_haftalari = [h for h in seri if h["veri_var"]]
    if len(veri_haftalari) >= 2:
        onceki = veri_haftalari[-2]["olay"]
        simdi = veri_haftalari[-1]["olay"]
        # Sayıya ek getirmekten kaçınılıyor: Türkçede ek sayının son hecesine
        # göre değişiyor (10'du, 3'tü, 5'ti) ve tek kalıpla doğru yazılamıyor.
        if onceki and simdi > onceki * 1.25:
            maddeler.append(
                f"Bu hafta <strong>{simdi} olay</strong> yaşandı (geçen hafta {onceki}) — "
                "belirgin bir artış var, sebebini araştırmak gerekir."
            )
        elif onceki and simdi < onceki * 0.75:
            maddeler.append(
                f"Bu hafta <strong>{simdi} olay</strong> yaşandı (geçen hafta {onceki}) — "
                "durum geçen haftaya göre iyileşti."
            )
        else:
            maddeler.append(
                f"Olay sayısı geçen haftayla benzer seviyede: bu hafta {simdi}, "
                f"geçen hafta {onceki}. Olağandışı bir durum yok."
            )
    else:
        maddeler.append(
            "Karşılaştırma için henüz yeterli geçmiş yok. Birkaç hafta sonra bu bölüm "
            "\"geçen haftaya göre iyileşti / kötüleşti\" diyebilecek."
        )


    surekli = [h for h in sorunlu if h["uptime_pct"] < 50]
    if surekli:
        adlar = ", ".join(_kisa_ad(h["name"]) for h in surekli)
        maddeler.append(
            f"<strong>{adlar}</strong> hafta boyunca büyük ölçüde erişilemez durumdaydı. "
            "Bu yurtlarda yerinde müdahale gerekiyor."
        )

    toplam = sum(n for _, n in bolge) or 1
    if bolge and bolge[0][1] / toplam > 0.4 and bolge[0][1] >= 3:
        maddeler.append(
            f"Sorunların %{bolge[0][1] / toplam * 100:.0f}'i "
            f"<strong>{esc(bolge[0][0])}</strong> bölgesinde toplandı."
        )

    # Kendiliğinden geçmiş kısa dalgalanmalar tek satırda özetlenir: gizlenmez
    # ama yönetici raporunun başına konup gerçek sorunları bastırmaz da.
    onemsiz = sinif["onemsiz"]
    if onemsiz:
        maddeler.append(
            f"Ayrıca <strong>{len(onemsiz)} kısa dalgalanma</strong> yaşandı ve hepsi "
            "birkaç dakika içinde kendiliğinden düzeldi. Bunlar müdahale gerektirmez; "
            "tekrar edenler yukarıdaki erken uyarı bölümünde ayrıca listelenir."
        )

    if izleme_eksigi:
        # Dürüstlük gereği söylenir ama "yurt sorunu" sayılmaz: bu yurtlarda
        # internet çalışıyor, ölçemediğimiz şey trafik miktarı.
        maddeler.append(
            f"<strong>{len(izleme_eksigi)} yurtta izleme eksiği var</strong> "
            f"({esc(', '.join(_kisa_ad(a) for a in izleme_eksigi))}). Bu yurtlarda internet "
            "çalışıyor; ölçemediğimiz şey ne kadar trafik geçtiği. Yurt arızası değil, "
            "izleme kurulumunun tamamlanması gereken bir eksiği."
        )

    if not maddeler:
        maddeler.append("Bu hafta öne çıkan bir sorun yok, ağ istikrarlı çalıştı.")

    return "<ul style='margin:0;padding-left:19px;line-height:1.8;font-size:13.5px'>" + "".join(
        f"<li style='margin-bottom:7px'>{m}</li>" for m in maddeler
    ) + "</ul>"


def _kisa_ad(ad: str | None) -> str:
    """TUGVA-KIRSEHIR-AHI-T25 -> "Kırşehir Ahi".

    Yöneticiye cihaz modeli değil yer lazım. İl adı, host adındaki ASCII
    yazımdan değil il tablosundan alınır; aksi halde "Kirsehir" gibi
    Türkçe karakterleri eksik adlar çıkıyor.
    """
    if not ad:
        return "—"
    il, _ = regions.parse_host_name(ad)
    parcalar = [p for p in ad.split("-") if p and p.upper() != "TUGVA"]
    if len(parcalar) > 1:
        parcalar = parcalar[:-1]  # sondaki model kodunu at

    if il:
        # İl adını doğru yazımıyla koy, kalan ayırt edici parçaları ekle.
        normal_il = regions.normalize(il)
        kalan = [regions.gorunen(p) for p in parcalar if regions.normalize(p) != normal_il]
        return " ".join([regions.gorunen(il), *kalan])
    return " ".join(regions.gorunen(p) for p in parcalar) or ad


# ============================================================= TEKNİK RAPOR


def teknik(store: Store, config: dict[str, Any], logo: str, now: int | None = None) -> str:
    """Teknik servis raporu.

    Sayfanın merkezi arıza kayıt dökümüdür: her kaydın ne zaman başladığı,
    bittiği, kaç kez tekrarladığı, hangi ölçümden ve hangi eşikten çıktığı,
    o anda hattın değerlerinin ne olduğu tek satırın altında toplanır. Grafikler
    ve yurt tablosu bunun bağlamı; asıl iş kayıtlarda.
    """
    now = now or int(time.time())
    v = _hafta(store, config, now)
    hosts, incidents = v["hosts"], v["incidents"]
    th = config["thresholds"]

    uptime = sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    kesinti = sum(
        ariza_suresi(i, now) for i in incidents if i.code in KESINTI_KODLARI
    )
    gecikmeler = [h["avg_latency"] for h in hosts if h["avg_latency"]]

    # Her sayının paydası: "120 kayıt" tek başına ne kadar olduğunu anlatmıyor.
    gozlem = sum(h["gozlem_sn"] or 0 for h in hosts)
    izleme = [i for i in incidents if i.code in IZLEME_KODLARI]
    yurt_sorunu = [i for i in incidents if i.code not in IZLEME_KODLARI]
    sure = lambda liste: sum(ariza_suresi(i, now) for i in liste)  # noqa: E731
    etkilenen = len({i.hostid for i in incidents if i.hostid})
    oran = (lambda s: f"%{s / gozlem * 100:.2f}" if gozlem else "—")
    acik = [i for i in incidents if i.ended_at is None]

    govde = [
        "<h1>Teknik Servis Raporu</h1>",
        f'<p class="alt">{esc(fmt_time(v["since"]))} – {esc(fmt_time(now))} · '
        f'{len(hosts)} yurt · {v["total_checks"]:,} ölçüm · '
        f'{esc(fmt_duration(gozlem))} toplam gözlem · '
        f'kontrol aralığı {config["poll"]["check_interval_minutes"]} dk · '
        f'ön tanı {len(VERI_KAYNAGI)} kural</p>'.replace(",", "."),
        pages.kpi(
            [
                (fmt_pct(uptime, 2), "Ortalama erişilebilirlik", "planlı kapatmalar hariç"),
                (
                    fmt_duration(kesinti),
                    "Toplam kesinti",
                    f"{' + '.join(KESINTI_KODLARI)}<br>gözlem süresinin {oran(kesinti)}'i",
                ),
                (
                    f"{len(incidents)}",
                    "Açılan arıza kaydı",
                    f"{etkilenen} / {len(hosts)} yurtta · {v['total_checks']:,} ölçüm içinde"
                    .replace(",", ".")
                    + f'<div style="margin-top:7px">'
                    f"<strong>{len(yurt_sorunu)}</strong> yurt sorunu "
                    f"({oran(sure(yurt_sorunu))}) · "
                    f"<strong>{len(izleme)}</strong> izleme eksiği "
                    f"({oran(sure(izleme))})</div>",
                ),
                (
                    f"{len(acik)}",
                    "Hâlâ açık kayıt",
                    "kapanmamış, müdahale bekliyor" if acik else "tümü kapandı",
                ),
            ]
        ),
    ]

    # Sayfanın merkezi: tam kayıt dökümü. Grafiklerden önce geliyor — servise
    # bakan kişi buraya bakmak için giriyor, aşağı kaydırmak zorunda kalmasın.
    govde.append(
        pages.kart(
            "Arıza kayıt dökümü",
            _servis_kayitlari(store, incidents, config, now),
            aciklama=(
                "Her satır bir arıza kaydıdır. Satıra tıklayınca tam teknik döküm "
                "açılır: sebep, önerilen müdahale, ölçümün geldiği Zabbix item'ı, "
                "aşılan eşik ve kaydın açıldığı andaki hat değerleri."
            ),
        )
    )

    gunluk = [(_gun_etiketi(g["gun"]), g["ariza_adet"]) for g in v["gunler"]]
    govde.append(
        pages.kart(
            "Güne göre açılan arıza kaydı",
            pages.sutun_grafik(gunluk),
            aciklama=(
                "Her gün kaç yeni arıza kaydı açıldığı. Bir kayıt, bulgu arka arkaya "
                f"{th.get('confirm_cycles', 2)} turda görüldükten sonra açılır; "
                "anlık dalgalanmalar kayıt üretmez."
            ),
        )
    )

    iki = [
        pages.kart(
            "Arıza tipleri",
            pages.yatay_grafik(
                [(CODE_LABEL.get(r["code"], r["code"]), r["n"]) for r in v["by_code"]][:10]
            ),
            aciklama="Ön tanı motorunun ürettiği kod bazında dağılım.",
        ),
        pages.kart(
            "Bölgelere göre arıza",
            pages.yatay_grafik([(r["region"] or "—", r["n"]) for r in v["by_region"]][:10]),
            aciklama="Bölge, host adındaki ilden türetilir.",
        ),
    ]
    govde.append(f'<div class="izgara">{"".join(iki)}</div>')

    govde.append(
        pages.kart(
            "Tüm yurtların haftalık ölçümleri",
            _teknik_host_tablo(hosts),
            aciklama=(
                "Erişilebilirlik, başarılı kontrol turlarının oranıdır. Bilinçli kapalı "
                "işaretli dönemler bu hesaba katılmaz. Tepe doluluk yalnızca trafik "
                "verisi gelen yurtlarda ölçülebilir."
            ),
        )
    )

    govde.append(
        pages.kart(
            "Ön tanı kuralları ve eşikleri",
            _kural_tablosu(th),
            aciklama=(
                "Motorun kullandığı tüm kurallar. Bir kaydın neden açıldığını "
                "tartışırken buradaki eşik değeri esastır; eşikler config.yaml "
                "içindeki thresholds bölümünden değiştirilir."
            ),
        )
    )

    govde.append(
        pages.kart(
            "İzleme altyapısının sağlığı",
            _izleme_sagligi(hosts, incidents, store.izleme_bosluklari(v["since"], now)),
            aciklama=(
                "Bunlar yurt arızası değil, izleme kurulumunun eksikleridir. "
                "İzlemenin kendisi durduysa en üstte yazar."
            ),
        )
    )

    return pages.shell(
        baslik="Teknik Servis Raporu — Yurt İnterneti",
        aktif="/teknik",
        govde="\n".join(govde),
        logo=logo,
        ek_css=SERVIS_CSS,
    )


# Kayıt dökümünün kendi stili: paylaşılan temaya girmiyor, yalnız bu sayfada
# kullanılıyor.
SERVIS_CSS = """
.servis-arac{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
.servis-arac input,.servis-arac select{background:var(--plane);color:var(--ink);
  border:1px solid var(--line);border-radius:8px;padding:7px 10px;font-size:13px;
  font-family:inherit}
.servis-arac input{min-width:210px;flex:1}
.servis-arac .sonuc{font-size:12px;color:var(--muted)}
table.servis tr.kayit{cursor:pointer}
table.servis tr.kayit:hover td{background:var(--plane)}
table.servis tr.kayit td{vertical-align:top}
table.servis tr.gizli{display:none}
table.servis tr.detay>td{background:var(--plane);
  border-top:0;padding:0 12px 16px}
.acilir{display:inline-block;width:14px;color:var(--muted);font-size:11px}
.dgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px 24px;
  padding-top:12px}
.dgrid dl{margin:0}
.dgrid dt{font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;
  color:var(--muted);margin-bottom:3px}
.dgrid dd{margin:0 0 11px;font-size:12.8px;line-height:1.55}
.dgrid code{font-size:11.5px}
.olcum-serit{display:flex;flex-wrap:wrap;gap:0 22px;margin-top:2px}
.olcum-serit span{font-size:12.5px}
.olcum-serit b{font-variant-numeric:tabular-nums}
"""

# Tıklayınca detay satırını açar; arama kutusu ve durum seçimi satırları filtreler.
# Harici kütüphane yok — sunucu kapalı ağda çalışıyor.
SERVIS_JS = """
<script>
(function(){
  var tablo=document.getElementById('servis');
  if(!tablo) return;
  tablo.addEventListener('click',function(e){
    var tr=e.target.closest('tr.kayit'); if(!tr) return;
    var d=tr.nextElementSibling;
    if(!d||!d.classList.contains('detay')) return;
    var kapali=d.classList.toggle('gizli');
    tr.querySelector('.acilir').textContent=kapali?'\\u25b8':'\\u25be';
  });
  var ara=document.getElementById('servis-ara'),
      durum=document.getElementById('servis-durum'),
      sonuc=document.getElementById('servis-sonuc');
  function suz(){
    var q=(ara.value||'').toLocaleLowerCase('tr'), d=durum.value, n=0;
    tablo.querySelectorAll('tr.kayit').forEach(function(tr){
      var uygun=(!q||tr.dataset.ara.indexOf(q)>=0)&&(!d||tr.dataset.durum===d);
      tr.style.display=uygun?'':'none';
      var det=tr.nextElementSibling;
      if(det&&det.classList.contains('detay')){
        det.style.display=uygun?'':'none';
        if(!uygun) det.classList.add('gizli');
      }
      if(uygun) n++;
    });
    sonuc.textContent=n+' kayıt';
  }
  ara.addEventListener('input',suz); durum.addEventListener('change',suz); suz();
})();
</script>
"""


def _servis_kayitlari(store: Store, incidents: list, config: dict[str, Any], now: int) -> str:
    """Arıza kayıtlarının tam dökümü: özet satır + açılır teknik detay."""
    if not incidents:
        return '<p class="bos">Bu dönemde arıza kaydı açılmadı.</p>'

    th = config["thresholds"]
    # Sıklık aynı yurt + aynı kod üzerinden sayılır; dedup_key zaten bu ikisini
    # birleştiriyor ve motorun tekrar saymasını engellediği anahtarla aynı.
    sayac: dict[str, int] = {}
    for i in incidents:
        sayac[i.dedup_key] = sayac.get(i.dedup_key, 0) + 1

    # Açık kayıtlar önce, sonra en uzun sürenler: müdahale sırası budur.
    sirali = sorted(
        incidents,
        key=lambda i: (i.ended_at is not None, -ariza_suresi(i, now)),
    )[:200]

    satirlar = []
    for i in sirali:
        acik = i.ended_at is None
        sure_sn = ariza_suresi(i, now)
        tekrar = sayac.get(i.dedup_key, 1)
        durum_kod, durum_yazi = ("kritik", "Açık") if acik else ("iyi", "Kapandı")
        ara_metni = " ".join(
            str(x or "").lower()
            for x in (i.name, i.host, i.region, i.code, CODE_LABEL.get(i.code, ""), i.title)
        )
        satirlar.append(
            f"""<tr class="kayit" data-durum="{'acik' if acik else 'kapali'}"
    data-ara="{esc(ara_metni)}">
  <td><span class="acilir">▸</span></td>
  <td class="sonuk sayi">#{i.id}</td>
  <td><strong>{esc(_kisa_ad(i.name) if i.name else (i.region or '—'))}</strong>
      <div class="sonuk" style="font-size:11.5px">{esc(i.host or i.name or '—')}</div></td>
  <td class="sonuk">{esc(i.region or '—')}</td>
  <td><code style="font-size:11.5px">{esc(i.code)}</code>
      <div style="font-size:11.5px">{esc(CODE_LABEL.get(i.code, i.code))}</div></td>
  <td>{pages.rozet(_SEVIYE_ROZET.get(i.severity, 'uyari'), _SEVIYE_ADI.get(i.severity, i.severity))}</td>
  <td class="sayi sonuk">{esc(fmt_time(i.started_at))}</td>
  <td class="sayi sonuk">{esc(fmt_time(i.ended_at)) if i.ended_at else '<span class="sonuk">—</span>'}</td>
  <td class="sayi">{esc(fmt_duration(sure_sn))}</td>
  <td class="sayi">{tekrar}×</td>
  <td>{pages.rozet(durum_kod, durum_yazi)}</td>
</tr>
<tr class="detay gizli"><td colspan="11">{_kayit_detayi(store, i, th, now, tekrar)}</td></tr>"""
        )

    ek = (
        f'<p class="ipucu">İlk 200 kayıt gösteriliyor (toplam {len(incidents)}).</p>'
        if len(incidents) > 200
        else ""
    )
    return (
        '<div class="servis-arac">'
        '<input id="servis-ara" type="search" placeholder="Yurt, kod veya bölge ara…" '
        'autocomplete="off">'
        '<select id="servis-durum">'
        '<option value="">Tüm kayıtlar</option>'
        '<option value="acik">Yalnız açık</option>'
        '<option value="kapali">Yalnız kapanmış</option>'
        "</select>"
        '<span class="sonuc" id="servis-sonuc"></span></div>'
        '<div class="sar"><table class="servis" id="servis">'
        "<tr><th></th><th>Kayıt</th><th>Yurt</th><th>Bölge</th><th>Kod</th>"
        "<th>Seviye</th><th>Başlangıç</th><th>Bitiş</th><th>Süre</th>"
        "<th>Sıklık</th><th>Durum</th></tr>"
        + "".join(satirlar)
        + "</table></div>"
        + ek
        + SERVIS_JS
    )


_SEVIYE_ROZET = {"critical": "kritik", "warning": "uyari", "info": "iyi"}
_SEVIYE_ADI = {"critical": "Kritik", "warning": "Uyarı", "info": "Bilgi"}


def _kayit_detayi(store: Store, i, th: dict[str, Any], now: int, tekrar: int) -> str:
    """Bir arıza kaydının tam teknik dökümü."""
    kaynak = VERI_KAYNAGI.get(i.code, {})
    try:
        esik = kaynak["esik"](th) if kaynak.get("esik") else "—"
    except Exception:
        esik = "—"

    baglam = store.olcum_baglami(i.hostid, i.started_at) if i.hostid else None
    olcum = _olcum_serit(baglam)

    bildirim = (
        f"{esc(fmt_time(i.notified_at))} · mail gönderildi"
        if i.notified_at
        else "Gönderilmedi (eşik/soğuma filtresine takıldı ya da kayıt kısa sürdü)"
    )
    mudahale = (
        "Uzaktan çözülebilir" if i.remote_fixable else "Yerinde müdahale gerekebilir"
    )

    alanlar = [
        ("Ne oldu", esc(i.title or "—")),
        ("Neden kaynaklanabilir", esc(i.detail or "—")),
        ("Önerilen müdahale", f"{esc(i.action or '—')}<br><span class='sonuk'>{mudahale}</span>"),
        ("Bilginin kaynağı", f"<code>{esc(kaynak.get('item', '—'))}</code>"),
        ("Neye bakıldı", esc(kaynak.get("olcut", "—"))),
        ("Aşılan eşik", esc(esik)),
        ("Kararı veren kural", f"<code>diagnose.{esc(kaynak.get('kural', '—'))}</code>"),
        ("Kayıt açıldığındaki ölçüm", olcum),
        ("Kayıt kimliği", f"<code>{esc(i.dedup_key)}</code> · #{i.id}"),
        ("İlk görülme", esc(fmt_time(i.started_at))),
        ("Son görülme", esc(fmt_time(i.last_seen))),
        ("Kapanış", esc(fmt_time(i.ended_at)) if i.ended_at else "Hâlâ açık"),
        ("Bu dönemdeki tekrarı", f"{tekrar} kez"),
        ("Bildirim", bildirim),
        ("Zabbix host", f"<code>{esc(i.host or '—')}</code> · hostid {esc(i.hostid or '—')}"),
        ("Kapsam", "Bölgesel" if i.scope == "region" else "Tek yurt"),
    ]
    return (
        '<div class="dgrid">'
        + "".join(f"<dl><dt>{ad}</dt><dd>{deger}</dd></dl>" for ad, deger in alanlar)
        + "</div>"
    )


def _olcum_serit(m: dict[str, Any] | None) -> str:
    """Arıza anındaki hat değerleri.

    Ölçüm satırı arıza kaydında saklanmıyor; measurements tablosundan o ana en
    yakın kayıt okunuyor. Yakınında ölçüm yoksa dürüstçe söylenir.
    """
    if not m:
        return '<span class="sonuk">O ana ait ölçüm bulunamadı.</span>'
    # Ping cevapsızken kaydedilen gecikme 0'dır; "0 ms" yazmak "çok hızlı" gibi
    # okunuyor, oysa ölçüm yok demek.
    erisim = bool(m.get("reachable"))
    parcalar = [
        ("Ping", "cevap var" if erisim else "cevap yok"),
        ("Gecikme", fmt_ms(m.get("latency_ms")) if erisim else "ölçülemedi"),
        ("Kayıp", fmt_pct(m.get("loss_pct"))),
    ]
    if m.get("in_bps") is not None or m.get("out_bps") is not None:
        parcalar.append(("İndirme", fmt_bps(m.get("in_bps"))))
        parcalar.append(("Yükleme", fmt_bps(m.get("out_bps"))))
    if m.get("util_pct") is not None:
        parcalar.append(("Doluluk", fmt_pct(m.get("util_pct"), 0)))
    if m.get("cpu_pct") is not None:
        parcalar.append(("CPU", fmt_pct(m.get("cpu_pct"), 0)))
    if m.get("mem_pct") is not None:
        parcalar.append(("Bellek", fmt_pct(m.get("mem_pct"), 0)))
    if m.get("if_errors") is not None:
        parcalar.append(("Arayüz hata sayacı", f"{m['if_errors']:.0f}"))
    if m.get("planned"):
        parcalar.append(("Not", "bilinçli kapalı işaretliydi"))
    return (
        '<div class="olcum-serit">'
        + "".join(f"<span>{ad} <b>{esc(d)}</b></span>" for ad, d in parcalar)
        + f'</div><div class="sonuk" style="font-size:11px;margin-top:4px">'
        f'ölçüm zamanı {esc(fmt_time(m["ts"]))}</div>'
    )


def _kural_tablosu(th: dict[str, Any]) -> str:
    """Motorun tüm kuralları ve yürürlükteki eşikleri."""
    satirlar = []
    for kod, k in VERI_KAYNAGI.items():
        try:
            esik = k["esik"](th)
        except Exception:
            esik = "—"
        satirlar.append(
            f"""<tr>
  <td><code style="font-size:11.5px">{esc(kod)}</code></td>
  <td>{esc(CODE_LABEL.get(kod, kod))}</td>
  <td><code style="font-size:11.5px">{esc(k['item'])}</code></td>
  <td>{esc(k['olcut'])}</td>
  <td>{esc(esik)}</td>
</tr>"""
        )
    return (
        '<div class="sar"><table><tr><th>Kod</th><th>Arıza</th><th>Zabbix item</th>'
        "<th>Neye bakılır</th><th>Eşik</th></tr>"
        + "".join(satirlar)
        + "</table></div>"
    )


def _teknik_host_tablo(hosts: list[dict]) -> str:
    if not hosts:
        return '<p class="bos">Veri yok.</p>'
    sirali = sorted(hosts, key=lambda h: (h["uptime_pct"], -(h["avg_loss"] or 0)))
    satirlar = []
    for h in sirali:
        if h["uptime_pct"] >= 99.9:
            d, y = "iyi", "Normal"
        elif h["uptime_pct"] >= 99:
            d, y = "uyari", "Uyarı"
        else:
            d, y = "kritik", "Kritik"
        satirlar.append(
            f"""<tr>
  <td>{esc(h['name'])}</td>
  <td class="sonuk">{esc(h['region'])}</td>
  <td>{pages.rozet(d, y)}</td>
  <td class="sayi">{esc(fmt_pct(h['uptime_pct'], 2))}</td>
  <td class="sayi">{esc(h['down'])} / {esc(h['checks'])}</td>
  <td class="sayi">{esc(fmt_ms(h['avg_latency']))}</td>
  <td class="sayi">{esc(fmt_pct(h['avg_loss']))}</td>
  <td class="sayi">{esc(fmt_pct(h['peak_util'], 0)) if h['peak_util'] else '<span class="sonuk">—</span>'}</td>
</tr>"""
        )
    return (
        '<div class="sar"><table><tr><th>Yurt</th><th>Bölge</th><th>Durum</th>'
        "<th>Erişilebilirlik</th><th>Başarısız</th><th>Ort. gecikme</th>"
        "<th>Ort. kayıp</th><th>Tepe doluluk</th></tr>"
        + "".join(satirlar)
        + "</table></div>"
    )


def _izleme_sagligi(hosts: list[dict], incidents: list,
                    bosluklar: list[tuple[int, int]] | None = None) -> str:
    """İzlemenin kendi eksikleri — arıza sanılıp kovalanmasın diye ayrı bölüm."""
    veri_yok = sorted({i.name for i in incidents if i.code == "NO_IF_DATA" and i.name})
    bayat = sorted({i.name for i in incidents if i.code == "STALE_DATA" and i.name})
    kapasitesiz = [h for h in hosts if not h["peak_util"]]

    satirlar = []
    if veri_yok:
        satirlar.append(
            f"<li><strong>SNMP arayüz verisi gelmeyen {len(veri_yok)} yurt:</strong> "
            f"{esc(', '.join(veri_yok))}. Ping tabanlı tespit çalışır, trafik ve "
            "hat doluluğu ölçülemez. Cihazda SNMP servisi ve Zabbix'e izin veren "
            "politika kontrol edilmeli.</li>"
        )
    if bayat:
        satirlar.append(
            f"<li><strong>Verisi geciken {len(bayat)} yurt:</strong> {esc(', '.join(bayat))}. "
            "Zabbix poller kuyruğu incelenmeli.</li>"
        )
    if kapasitesiz:
        satirlar.append(
            f"<li><strong>Hat kapasitesi henüz bilinmeyen {len(kapasitesiz)} yurt.</strong> "
            "Doluluk oranı, yeterli trafik geçmişi biriktikçe otomatik tahmin edilir; "
            "gerçek abonelik hızları girilirse kesinleşir.</li>"
        )
    # İzlemenin durduğu aralıklar en başta yazılır: o süre boyunca yurtlarda ne
    # olduğu bilinmiyor ve raporun geri kalanı o dönemi kapsamıyor.
    if bosluklar:
        toplam = sum(b - a for a, b in bosluklar)
        detay = "; ".join(
            f"{esc(fmt_time(a))} – {esc(fmt_time(b))} ({esc(fmt_duration(b - a))})"
            for a, b in bosluklar[-5:]
        )
        satirlar.insert(0, (
            f"<li><strong>İzleme {len(bosluklar)} kez durdu, toplam "
            f"{esc(fmt_duration(toplam))}.</strong> {detay}. Bu aralıklarda ölçüm "
            "alınmadı; yurtlarda sorun yaşandıysa bu raporda görünmez. Arıza "
            "süreleri de sorunun en son görüldüğü ana kadar sayılır, boşluk "
            "kesintiye yazılmaz.</li>"
        ))

    if not satirlar:
        satirlar.append("<li>İzleme altyapısında eksik yok, tüm yurtlardan tam veri geliyor.</li>")

    return (
        "<ul style='margin:0;padding-left:19px;line-height:1.7;font-size:13px'>"
        + "".join(satirlar)
        + "</ul>"
    )
