"""Zabbix'ten gelen ham item verisini yurt bazlı ölçüm anlık görüntüsüne dönüştürür.

Gerçek envantere göre tasarlandı: her yurt tek host (WatchGuard firewall),
`Network Generic Device by SNMP` şablonu. Cihazlarda CPU/bellek item'ı yok;
buna karşılık arayüz bazında trafik, hız, durum ve hata sayaçları var.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import regions as region_lookup
from .zabbix import ZabbixClient

log = logging.getLogger(__name__)

# "Interface eth7(): Bits received" -> eth7
IFACE_NAME = re.compile(r"Interface\s+(.+?)\s*\(")
# net.if.in[ifInOctets.4097] -> 4097
IFACE_INDEX = re.compile(r"\[[^.\]]*\.(\d+)\]")

# WAN adayı olamayacak arayüzler (tünel, loopback, sanal).
NON_WAN_PREFIXES = ("tun", "lo", "vlan", "br", "ipsec", "ppp0.", "sw")


@dataclass
class Interface:
    """Bir cihazdaki tek bir ağ arayüzü."""

    key: str                      # SNMP index
    name: str                     # eth0, eth7, sw10 …
    in_bps: float | None = None
    out_bps: float | None = None
    speed_bps: float | None = None
    status: int | None = None     # 1 = up, 2 = down
    errors: float = 0.0

    @property
    def is_up(self) -> bool | None:
        return None if self.status is None else self.status == 1

    @property
    def total_bps(self) -> float:
        return (self.in_bps or 0.0) + (self.out_bps or 0.0)

    @property
    def download_dominant(self) -> bool:
        """WAN bacağında indirme, LAN bacağında gönderme baskındır."""
        if self.in_bps is None or self.out_bps is None:
            return False
        return self.in_bps > self.out_bps


@dataclass
class HostSnapshot:
    """Bir yurdun tek bir kontrol anındaki durumu."""

    hostid: str
    host: str
    name: str
    region: str
    address: str
    ts: int

    province: str | None = None
    reachable: bool | None = None
    loss_pct: float | None = None
    latency_ms: float | None = None
    cpu_pct: float | None = None
    mem_pct: float | None = None
    uptime_seconds: float | None = None

    interfaces: dict[str, Interface] = field(default_factory=dict)
    wan: str | None = None            # WAN olarak seçilen arayüzün adı
    wan_auto: bool = True             # otomatik mi seçildi, elle mi verildi

    in_bps: float | None = None       # WAN arayüzünün trafiği
    out_bps: float | None = None
    if_errors: float | None = None    # tüm arayüzlerin hata/discard toplamı

    capacity_mbps: float | None = None   # bilinmiyorsa None
    capacity_estimated: bool = False     # geçmiş veriden öğrenildiyse True

    has_data: bool = False
    has_interface_data: bool = False
    stale_seconds: int | None = None
    problems: list[dict[str, Any]] = field(default_factory=list)

    @property
    def util_pct(self) -> float | None:
        """Hat doluluğu. Kapasite bilinmiyorsa None."""
        if self.capacity_mbps is None or self.capacity_mbps <= 0:
            return None
        busiest = max(self.in_bps or 0.0, self.out_bps or 0.0)
        return busiest / (self.capacity_mbps * 1_000_000) * 100.0

    @property
    def down_interfaces(self) -> list[str]:
        return sorted(i.name for i in self.interfaces.values() if i.is_up is False)


def _matches(key: str, prefixes: list[str]) -> bool:
    return any(key.startswith(p) for p in prefixes)


def resolve_region(host: dict[str, Any], region_config: dict[str, Any]) -> tuple[str | None, str]:
    """(il, bölge) döner. Sırayla: host tag -> host grubu ön eki -> host adındaki il."""
    tag_name = (region_config.get("tag") or "").lower()
    if tag_name:
        for tag in host.get("tags") or []:
            if tag.get("tag", "").lower() == tag_name and tag.get("value"):
                return None, tag["value"]

    prefix = region_config.get("host_group_prefix") or ""
    if prefix:
        for group in host.get("groups") or []:
            name = group.get("name", "")
            if name.startswith(prefix):
                trimmed = name[len(prefix) :].strip("/ ")
                if trimmed:
                    return None, trimmed

    if region_config.get("from_host_name", True):
        province, region = region_lookup.parse_host_name(host.get("host", ""))
        if region:
            return province, region

    return None, region_config.get("default", "Bilinmiyor")


def collect(
    client: ZabbixClient, config: dict[str, Any], capacity_lookup=None
) -> list[HostSnapshot]:
    """Tüm yurtlar için tek bir kontrol turu çalıştırır.

    capacity_lookup: hostid -> tahmini kapasite (Mbps) döndüren isteğe bağlı fonksiyon.
    Store üzerinden geçmiş trafikten öğrenilen kapasite buradan geçirilir.
    """
    now = int(time.time())
    window = config["poll"]["history_window_minutes"] * 60

    hosts = client.get_hosts(config["zabbix"]["host_groups"])
    hosts = _apply_exclusions(hosts, config["zabbix"].get("exclude_hosts") or [])
    if not hosts:
        log.warning("Zabbix'te izlenecek host bulunamadı.")
        return []

    host_ids = [h["hostid"] for h in hosts]
    items = client.get_items(host_ids)
    last_values = client.get_last_values(items, window)

    try:
        problems_by_host = client.map_events_to_hosts(client.get_problems(host_ids))
    except Exception as exc:
        log.warning("Zabbix problem listesi alınamadı: %s", exc)
        problems_by_host = {}

    items_by_host: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_by_host.setdefault(item["hostid"], []).append(item)

    return [
        _build_snapshot(
            host=host,
            items=items_by_host.get(host["hostid"], []),
            last_values=last_values,
            problems=problems_by_host.get(host["hostid"], []),
            config=config,
            capacity_lookup=capacity_lookup,
            now=now,
        )
        for host in hosts
    ]


def _apply_exclusions(hosts: list[dict], patterns: list[str]) -> list[dict]:
    """İzlemeye dahil olmaması gereken hostları (ör. Zabbix sunucusu) eler."""
    if not patterns:
        return hosts
    lowered = [p.lower() for p in patterns]
    return [
        h
        for h in hosts
        if not any(p in h["host"].lower() or p in (h.get("name") or "").lower() for p in lowered)
    ]


def _build_snapshot(
    *,
    host: dict[str, Any],
    items: list[dict[str, Any]],
    last_values: dict[str, tuple[float, int]],
    problems: list[dict[str, Any]],
    config: dict[str, Any],
    capacity_lookup,
    now: int,
) -> HostSnapshot:
    keys = config["item_keys"]
    province, region = resolve_region(host, config["regions"])
    display_name = host.get("name") or host["host"]

    snapshot = HostSnapshot(
        hostid=host["hostid"],
        host=host["host"],
        name=display_name,
        region=region,
        province=province,
        address=host.get("address", ""),
        ts=now,
        problems=problems,
    )

    newest_clock = 0
    for item in items:
        measured = last_values.get(item["itemid"])
        if measured is None:
            continue
        value, clock = measured
        newest_clock = max(newest_clock, clock)
        key = item["key_"]

        # Arayüz item'ları önce ayrıştırılır; kalanlar host geneli metriklerdir.
        if _assign_interface_value(snapshot, item, key, value, keys):
            continue

        # icmppingloss/icmppingsec, "icmpping" ile de eşleşir — sıralama önemli.
        if _matches(key, keys["loss"]):
            snapshot.loss_pct = value
        elif _matches(key, keys["latency"]):
            snapshot.latency_ms = value * 1000.0
        elif _matches(key, keys["ping"]):
            snapshot.reachable = value >= 1
        elif _matches(key, keys["cpu"]):
            snapshot.cpu_pct = value
        elif _matches(key, keys["mem"]):
            snapshot.mem_pct = value
        elif _matches(key, keys["uptime"]):
            # Birden fazla uptime item'ı olabilir; en büyüğü gerçeğe en yakındır.
            if snapshot.uptime_seconds is None or value > snapshot.uptime_seconds:
                snapshot.uptime_seconds = value

    snapshot.has_data = newest_clock > 0
    snapshot.has_interface_data = bool(snapshot.interfaces)
    if newest_clock:
        snapshot.stale_seconds = max(0, now - newest_clock)

    if snapshot.reachable is None and snapshot.has_data:
        snapshot.reachable = True

    _select_wan(snapshot, config)
    _resolve_capacity(snapshot, config, capacity_lookup)

    errors = sum(i.errors for i in snapshot.interfaces.values())
    snapshot.if_errors = errors if snapshot.interfaces else None

    return snapshot


def _assign_interface_value(
    snapshot: HostSnapshot, item: dict, key: str, value: float, keys: dict
) -> bool:
    """Arayüzle ilgili bir item ise kaydeder ve True döner."""
    metric = None
    for name, prefixes in (
        ("in", keys["if_in"]),
        ("out", keys["if_out"]),
        ("speed", keys["if_speed"]),
        ("status", keys["if_status"]),
        ("errors", keys["if_errors"]),
    ):
        if _matches(key, prefixes):
            metric = name
            break
    if metric is None:
        return False

    index_match = IFACE_INDEX.search(key)
    index = index_match.group(1) if index_match else key
    name_match = IFACE_NAME.search(item.get("name") or "")
    iface_name = name_match.group(1) if name_match else f"if{index}"

    iface = snapshot.interfaces.get(index)
    if iface is None:
        iface = Interface(key=index, name=iface_name)
        snapshot.interfaces[index] = iface

    if metric == "in":
        iface.in_bps = value
    elif metric == "out":
        iface.out_bps = value
    elif metric == "speed":
        iface.speed_bps = value
    elif metric == "status":
        iface.status = int(value)
    elif metric == "errors":
        iface.errors += value
    return True


def _select_wan(snapshot: HostSnapshot, config: dict[str, Any]) -> None:
    """İnternet (WAN) bacağını belirler.

    Cihazdan cihaza değiştiği için sabit bir isim varsayılamaz. Kural:
    indirmenin göndermeden baskın olduğu, en çok trafik alan fiziksel arayüz.
    Yapılandırmada elle verilmişse o kullanılır.
    """
    overrides = config.get("wan", {}).get("interfaces") or {}
    manual = overrides.get(snapshot.host) or overrides.get(snapshot.name)
    if manual:
        for iface in snapshot.interfaces.values():
            if iface.name == manual:
                snapshot.wan = iface.name
                snapshot.wan_auto = False
                snapshot.in_bps, snapshot.out_bps = iface.in_bps, iface.out_bps
                return
        log.warning(
            "%s için elle verilen WAN arayüzü '%s' bulunamadı, otomatik seçime dönülüyor.",
            snapshot.host, manual,
        )

    candidates = [
        i
        for i in snapshot.interfaces.values()
        if i.in_bps is not None
        and i.is_up is not False
        and not i.name.lower().startswith(NON_WAN_PREFIXES)
    ]
    if not candidates:
        return

    download_side = [i for i in candidates if i.download_dominant]
    pool = download_side or candidates
    wan = max(pool, key=lambda i: i.in_bps or 0.0)

    snapshot.wan = wan.name
    snapshot.wan_auto = True
    snapshot.in_bps, snapshot.out_bps = wan.in_bps, wan.out_bps


def _resolve_capacity(snapshot: HostSnapshot, config: dict[str, Any], capacity_lookup) -> None:
    """Hat kapasitesini belirler: elle > öğrenilmiş > kapalı.

    net.if.speed bilinçli olarak kullanılmaz: fiziksel port hızını (çoğunlukla
    1 Gbps) verir, ISP'den alınan gerçek hat hızını değil.
    """
    bandwidth = config["bandwidth"]
    mode = bandwidth.get("mode", "learned")

    manual = (bandwidth.get("per_host") or {}).get(snapshot.host) or (
        bandwidth.get("per_host") or {}
    ).get(snapshot.name)
    if manual:
        snapshot.capacity_mbps = float(manual)
        return

    if mode == "fixed":
        default = bandwidth.get("default_mbps")
        snapshot.capacity_mbps = float(default) if default else None
        return

    if mode == "learned" and capacity_lookup is not None:
        estimated = capacity_lookup(snapshot.hostid)
        if estimated:
            snapshot.capacity_mbps = estimated
            snapshot.capacity_estimated = True
