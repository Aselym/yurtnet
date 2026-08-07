"""Otomatik ön tanı motoru.

Her yurt için toplanan ölçümleri kural sırasına göre değerlendirip
"muhtemel sebep + önerilen aksiyon + uzaktan çözülebilir mi" çıkarır.
Kurallar önem sırasına göre denenir; ilk eşleşen ana tanı olur,
kalan eşleşmeler ek bulgu olarak listelenir.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .collect import HostSnapshot

SEVERITY_ORDER = {"ok": 0, "info": 1, "warning": 2, "critical": 3}


@dataclass
class Finding:
    """Bir yurt (veya bölge) için üretilmiş tanı."""

    code: str
    severity: str
    title: str
    detail: str
    action: str
    remote_fixable: bool
    hostid: str = ""
    host: str = ""
    name: str = ""
    region: str = ""
    scope: str = "host"                 # "host" | "region"
    extra: list[str] = field(default_factory=list)

    @property
    def severity_rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 0)

    @property
    def dedup_key(self) -> str:
        """Aynı arızanın tekrar tekrar maillenmesini engellemek için kimlik."""
        return f"{self.scope}:{self.hostid or self.region}:{self.code}"


Rule = Callable[[HostSnapshot, dict[str, Any], dict[str, Any]], Finding | None]

# ---------------------------------------------------------------- host kuralları
# Her kural ya bir Finding döner ya da None. Sıra = öncelik.


def _rule_planned(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    """Bilinçli kapatılmış yurt — arıza değil, bilgi.

    Yaz döneminde boş kalan yurtlarda internet kasıtlı olarak kapatılıyor.
    İşaretlenmezse hafta boyu "kritik arıza" olarak raporlanır ve
    erişilebilirlik ortalamasını yanlış biçimde aşağı çeker.
    """
    kayit = (ctx.get("planned") or {}).get(snap.hostid)
    if kayit is None:
        return None
    # Cihaz yeniden cevap veriyorsa bu kural devreye girmez; işareti
    # kaldırma kararını çağıran taraf verir (bkz. main._planli_temizle).
    if snap.reachable is True:
        return None

    sure = ""
    if kayit.get("since"):
        gecen = int(time.time()) - int(kayit["since"])
        sure = f" ({gecen // 86400} gündür)" if gecen >= 86400 else ""
    aciklama = (kayit.get("note") or "").strip()

    return Finding(
        code="PLANNED_DOWN",
        severity="info",
        title=f"Bilinçli kapalı{sure}",
        detail=(
            (f"Sebep: {aciklama}. " if aciklama else "")
            + "Bu yurdun interneti bilerek kapatıldığı için arıza sayılmıyor ve "
            "erişilebilirlik hesabına katılmıyor. Cihaz yeniden cevap vermeye "
            "başladığında bu işaret kendiliğinden kalkar."
        ),
        action="Bir şey yapmanız gerekmiyor.",
        remote_fixable=True,
    )


def _rule_no_data(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.has_data:
        return None
    return Finding(
        code="NO_DATA",
        severity="critical",
        title="Cihazdan veri gelmiyor",
        detail=(
            "Son kontrol penceresinde bu yurttan hiçbir ölçüm alınamadı. "
            "Cihaz kapalı, hat komple kopmuş veya Zabbix agent/SNMP erişimi kesilmiş olabilir."
        ),
        action=(
            "Önce hattın ISP tarafında kesinti kaydı var mı bakın. Yoksa yurtla telefonla "
            "iletişime geçip modem/firewall ışıklarını ve elektriği teyit ettirin."
        ),
        remote_fixable=False,
    )


def _rule_down(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.reachable is not False:
        return None
    return Finding(
        code="HOST_DOWN",
        severity="critical",
        title="İnternet kopuk (cihaz ping'e cevap vermiyor)",
        detail="ICMP ping başarısız. Yurt şu anda internete erişemiyor.",
        action=(
            "ISP kesinti kaydını kontrol edin, yedek hat varsa devreye alın. "
            "Çözülmezse yerinde müdahale planlayın."
        ),
        remote_fixable=False,
    )


def _rule_stale(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    # Veri var ama bayat: izleme akışı tıkanmış demektir.
    # Eşik kontrol aralığından bağımsız sabittir; aksi halde sık kontrolde
    # (ör. dakikada bir) tek bir gecikmiş ölçüm bile uyarı üretirdi.
    limit = th["stale_data_minutes"] * 60
    if snap.stale_seconds is None or snap.stale_seconds < limit:
        return None
    return Finding(
        code="STALE_DATA",
        severity="warning",
        title="İzleme verisi güncellenmiyor",
        detail=(
            f"En son ölçüm {snap.stale_seconds // 60} dakika önce alınmış. "
            "Hat ayakta olsa bile izleme akışında sorun var."
        ),
        action="Zabbix üzerinde ilgili host'un item'larını ve poller kuyruğunu kontrol edin.",
        remote_fixable=True,
    )


def _rule_wan_silent(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    # Cihaz ayakta ama WAN trafiği neredeyse sıfır -> ISP tarafı düşmüş olabilir.
    if snap.reachable is not True or snap.in_bps is None or snap.out_bps is None:
        return None
    if snap.in_bps + snap.out_bps > 8000:  # ~1 KB/s üzerindeyse trafik var sayılır
        return None
    return Finding(
        code="WAN_SILENT",
        severity="critical",
        title="Cihaz ayakta ama trafik yok",
        detail=(
            "Firewall/modem yönetimsel olarak erişilebilir durumda, fakat WAN üzerinde "
            "kayda değer trafik akmıyor. Genellikle ISP tarafı kopukluğunu veya "
            "PPPoE/oturum düşmesini gösterir."
        ),
        action=(
            "WAN arayüzünün durumunu ve PPPoE/DHCP oturumunu kontrol edin; "
            "uzaktan arayüzü reset etmeyi deneyin."
        ),
        remote_fixable=True,
    )


def _rule_packet_loss(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.loss_pct is None or snap.loss_pct < th["loss_warn"]:
        return None
    critical = snap.loss_pct >= th["loss_crit"]
    return Finding(
        code="PACKET_LOSS",
        severity="critical" if critical else "warning",
        title=f"Paket kaybı %{snap.loss_pct:.1f}",
        detail=(
            "Hat ayakta ancak paket kaybı yaşanıyor. Kullanıcı tarafında kopma, "
            "video/görüşme donması şeklinde hissedilir. Genellikle hat kalitesi "
            "(fiber/bakır), SFP veya ISP omurga sorunudur."
        ),
        action=(
            "Arayüz hata sayaçlarını kontrol edin, sorun sürüyorsa kayıpla birlikte "
            "ISP'ye hat kalitesi kaydı açın."
        ),
        remote_fixable=False,
    )


def _rule_latency(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.latency_ms is None or snap.latency_ms < th["latency_warn_ms"]:
        return None
    critical = snap.latency_ms >= th["latency_crit_ms"]
    return Finding(
        code="HIGH_LATENCY",
        severity="critical" if critical else "warning",
        title=f"Gecikme yüksek ({snap.latency_ms:.0f} ms)",
        detail=(
            "Ping süresi normalin üzerinde. Paket kaybı yoksa bu genellikle hat doluluğu "
            "ya da ISP yönlendirme değişikliğinden kaynaklanır."
        ),
        action="Aynı anda hat doluluğuna bakın; doluluk düşükse ISP'ye rota/gecikme kaydı açın.",
        remote_fixable=False,
    )


def _rule_saturation(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    util = snap.util_pct
    if util is None or util < th["bandwidth_util_warn"]:
        return None
    critical = util >= th["bandwidth_util_crit"]
    direction = "indirme" if (snap.in_bps or 0) >= (snap.out_bps or 0) else "yükleme"
    if snap.capacity_estimated:
        basis = (
            f"Kapasite ({snap.capacity_mbps:.0f} Mbps) geçmiş trafikten tahmin edildi; "
            "gerçek abonelik hızı girilirse bu oran kesinleşir."
        )
    else:
        basis = f"Hat kapasitesi {snap.capacity_mbps:.0f} Mbps olarak tanımlı."
    return Finding(
        code="SATURATION",
        severity="critical" if critical else "warning",
        title=f"Hat doluluğu %{util:.0f} ({direction})",
        detail=(
            "Hattın büyük kısmı kullanılıyor. Yavaşlık şikâyetlerinin en sık sebebi budur; "
            f"arıza değil kapasite sorunudur. {basis}"
        ),
        action=(
            "Trafiği en çok tüketen kaynakları firewall raporundan çıkarın. Sürekliyse "
            "kota/QoS uygulayın veya hat kapasitesi artırımı için talep açın."
        ),
        remote_fixable=True,
    )


def _rule_reboot(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    """Cihaz yakın zamanda yeniden başlamış — kısa kesintilerin en sık açıklaması."""
    limit = th["reboot_recent_minutes"] * 60
    if snap.uptime_seconds is None or snap.uptime_seconds <= 0 or snap.uptime_seconds > limit:
        return None
    minutes = int(snap.uptime_seconds // 60)
    return Finding(
        code="REBOOTED",
        severity="warning",
        title=f"Cihaz {minutes} dakika önce yeniden başlamış",
        detail=(
            "Firewall'ın çalışma süresi sıfırlanmış. Elektrik kesintisi, güç sorunu, "
            "firmware güncellemesi veya cihaz kilitlenmesi olabilir. Aynı yurtta sık "
            "tekrarlıyorsa donanım/güç sorunu güçlü ihtimaldir."
        ),
        action=(
            "Yurtta elektrik kesintisi olup olmadığını teyit edin. Tekrarlıyorsa UPS "
            "durumunu ve cihaz sıcaklığını kontrol ettirin."
        ),
        remote_fixable=False,
    )


def _rule_wan_down(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    """İnternet bacağı fiziksel olarak düşmüş."""
    if not snap.wan:
        return None
    iface = next((i for i in snap.interfaces.values() if i.name == snap.wan), None)
    if iface is None or iface.is_up is not False:
        return None
    return Finding(
        code="WAN_IFACE_DOWN",
        severity="critical",
        title=f"İnternet bacağı ({snap.wan}) kapalı",
        detail=(
            "Cihaza erişilebiliyor ama WAN arayüzü fiziksel olarak down durumda. "
            "Kablo çıkmış, SFP arızalı ya da ISP tarafındaki port kapanmış olabilir."
        ),
        action="Kablo/SFP kontrolü isteyin; sağlamsa ISP'ye port durumu için kayıt açın.",
        remote_fixable=False,
    )


def _rule_no_interface_data(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    """Ping çalışıyor ama SNMP arayüz verisi yok — izleme eksiği, arıza değil."""
    if snap.has_interface_data or snap.reachable is not True:
        return None
    return Finding(
        code="NO_IF_DATA",
        severity="info",
        title="Trafik verisi yok (SNMP arayüz keşfi eksik)",
        detail=(
            "Bu yurtta ping ile erişim var, internet çalışıyor. Ancak SNMP üzerinden "
            "arayüz verisi gelmediği için trafik ve hat doluluğu ölçülemiyor."
        ),
        action=(
            "Cihazda SNMP servisini ve Zabbix sunucusuna izin veren politikayı kontrol edin; "
            "ardından Zabbix'te arayüz keşfini bekleyin."
        ),
        remote_fixable=True,
    )


def _rule_if_errors(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    """Arayüz hata sayacındaki ARTIŞA bakar, mutlak değere değil.

    Sayaç kümülatiftir: cihaz açıldığından beri biriken toplamı gösterir.
    "Sıfırdan büyük mü" diye sorulursa, aylar önce olmuş beş hata yüzünden
    sağlıklı bir yurt her turda hatalı görünür. Anlamlı olan, iki ölçüm
    arasında yeni hata oluşup oluşmadığıdır.
    """
    if snap.if_errors is None:
        return None
    onceki = (ctx.get("onceki_if_errors") or {}).get(snap.hostid)
    if onceki is None:
        return None  # ilk ölçüm: kıyaslanacak geçmiş yok
    artis = snap.if_errors - onceki
    # Sayaç sıfırlanmışsa (cihaz yeniden başlamış) negatif çıkar — yok sayılır.
    if artis < th["if_error_artis_esigi"]:
        return None
    return Finding(
        code="IF_ERRORS",
        severity="warning",
        title=f"Arayüzde yeni hata: son kontrolde {artis:.0f} paket",
        detail=(
            f"Arayüz hata/discard sayacı {onceki:.0f}'dan {snap.if_errors:.0f}'a yükseldi. "
            "Yeni hata oluşuyor demektir; fiziksel katman sorununa (kablo, SFP, "
            "patch, duplex uyuşmazlığı) işaret eder."
        ),
        action="Port/kablo/SFP değişimi planlayın; duplex ve hız ayarlarını teyit edin.",
        remote_fixable=False,
    )


def _rule_cpu(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.cpu_pct is None or snap.cpu_pct < th["cpu_warn"]:
        return None
    return Finding(
        code="HIGH_CPU",
        severity="critical" if snap.cpu_pct >= th["cpu_crit"] else "warning",
        title=f"Firewall CPU %{snap.cpu_pct:.0f}",
        detail=(
            "Cihaz işlemcisi yüksek. Hat boş olsa bile trafiği işleyemediği için "
            "yavaşlık ve kopma hissi oluşur."
        ),
        action=(
            "Aktif oturum sayısını, IPS/AV taramasını ve olası saldırı/tarama trafiğini "
            "kontrol edin; gerekiyorsa uzaktan servis yeniden başlatın."
        ),
        remote_fixable=True,
    )


def _rule_memory(snap: HostSnapshot, th: dict, ctx: dict) -> Finding | None:
    if snap.mem_pct is None or snap.mem_pct < th["mem_warn"]:
        return None
    return Finding(
        code="HIGH_MEMORY",
        severity="critical" if snap.mem_pct >= th["mem_crit"] else "warning",
        title=f"Firewall bellek %{snap.mem_pct:.0f}",
        detail="Bellek kullanımı kritik seviyede; cihaz konservatif moda geçip trafik düşürebilir.",
        action="Oturum tablosunu ve log/rapor birikimini kontrol edin, planlı yeniden başlatma değerlendirin.",
        remote_fixable=True,
    )


HOST_RULES: list[Rule] = [
    _rule_planned,
    _rule_no_data,
    _rule_down,
    _rule_wan_down,
    _rule_wan_silent,
    _rule_packet_loss,
    _rule_saturation,
    _rule_latency,
    _rule_reboot,
    _rule_cpu,
    _rule_memory,
    _rule_if_errors,
    _rule_stale,
    _rule_no_interface_data,
]


def diagnose_host(snap: HostSnapshot, config: dict[str, Any], ctx: dict[str, Any]) -> list[Finding]:
    """Bir yurt için tüm kuralları çalıştırır, önem sırasına göre bulguları döner."""
    thresholds = config["thresholds"]
    findings: list[Finding] = []
    for rule in HOST_RULES:
        finding = rule(snap, thresholds, ctx)
        if finding is None:
            continue
        finding.hostid = snap.hostid
        finding.host = snap.host
        finding.name = snap.name
        finding.region = snap.region
        findings.append(finding)

    # Bilinçli kapatılmışsa geri kalan her şey (kopuk, veri yok…) beklenen durumdur.
    if any(f.code == "PLANNED_DOWN" for f in findings):
        return [f for f in findings if f.code == "PLANNED_DOWN"]

    # Cihaz komple erişilemezken alt metrikler anlamsız — gürültüyü kısalım.
    if any(f.code in ("NO_DATA", "HOST_DOWN") for f in findings):
        findings = [f for f in findings if f.code in ("NO_DATA", "HOST_DOWN")]

    # Zabbix'in kendi açık problemlerini ek bilgi olarak ilk bulguya iliştir.
    if findings and snap.problems:
        names = [p.get("name", "") for p in snap.problems[:5] if p.get("name")]
        if names:
            findings[0].extra.extend(f"Zabbix problemi: {n}" for n in names)

    findings.sort(key=lambda f: -f.severity_rank)
    return findings


def detect_flapping(
    snap: HostSnapshot, transitions_last_hour: int, config: dict[str, Any]
) -> Finding | None:
    """Saat içinde çok sayıda up/down değişimi = flapping."""
    limit = config["thresholds"]["flap_count_1h"]
    if transitions_last_hour < limit:
        return None
    return Finding(
        code="FLAPPING",
        severity="critical",
        title=f"Hat flapping ({transitions_last_hour} kez inip kalktı)",
        detail=(
            "Son 1 saatte bağlantı defalarca kopup geri geldi. Tek seferlik kesintiden "
            "daha ciddidir: genellikle hat kalitesi, güç sorunu veya arızalı SFP/modem işaretidir."
        ),
        action=(
            "Cihazın güç kaynağını ve fiziksel bağlantıyı kontrol ettirin; ISP'ye "
            "flapping kaydı açın. Yerinde müdahale gerekebilir."
        ),
        remote_fixable=False,
        hostid=snap.hostid,
        host=snap.host,
        name=snap.name,
        region=snap.region,
    )


def detect_regional_outage(
    snapshots: list[HostSnapshot], findings_by_host: dict[str, list[Finding]], config: dict[str, Any]
) -> list[Finding]:
    """Aynı bölgede çok sayıda yurt aynı anda düştüyse tek bir üst seviye tanı üret.

    Amaç: 30 ayrı 'kopuk' maili yerine 'bu bölgede omurga kesintisi var' demek.
    """
    minimum = config["thresholds"]["regional_outage_min_hosts"]
    by_region: dict[str, list[HostSnapshot]] = {}
    for snap in snapshots:
        # Bilinçli kapatılmış yurtlar bölge sayımına hiç girmez: ne kopuk
        # sayılırlar ne de "kaçta kaçı etkilendi" oranını seyreltirler.
        if any(f.code == "PLANNED_DOWN" for f in findings_by_host.get(snap.hostid, [])):
            continue
        by_region.setdefault(snap.region, []).append(snap)

    regional: list[Finding] = []
    for region, hosts in by_region.items():
        down = [
            s
            for s in hosts
            if any(f.code in ("NO_DATA", "HOST_DOWN") for f in findings_by_host.get(s.hostid, []))
        ]
        if len(down) < minimum:
            continue
        ratio = len(down) / len(hosts) * 100
        regional.append(
            Finding(
                code="REGIONAL_OUTAGE",
                severity="critical",
                title=f"{region}: bölgesel kesinti ({len(down)}/{len(hosts)} yurt kopuk)",
                detail=(
                    f"Bu bölgedeki yurtların %{ratio:.0f}'i aynı anda erişilemez durumda. "
                    "Tek tek yurt arızası olma ihtimali düşük; büyük olasılıkla ISP/omurga "
                    "kesintisi, bölgesel elektrik kesintisi veya merkezî bir yapılandırma hatası var."
                ),
                action=(
                    "Sahaya teknisyen göndermeden önce ISP ile bölgesel kesinti teyidi alın. "
                    f"Etkilenen yurtlar: {', '.join(s.name for s in down[:15])}"
                    + (" …" if len(down) > 15 else "")
                ),
                remote_fixable=False,
                region=region,
                scope="region",
            )
        )
    return regional
