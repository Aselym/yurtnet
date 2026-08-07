"""Zabbix envanter dökümü.

Amaç: kurulum öncesi "hangi hostlar var, nasıl adlandırılmış, hangi şablonlar
kullanılıyor, item key'leri ne" sorularını tek çalıştırmada cevaplamak.
Çıktısı düz metindir; item key eşlemesi ve yurt/cihaz gruplaması buna bakılarak yapılır.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .zabbix import ZabbixClient

# Cihaz rolü tahmini için host adında aranan ipuçları.
ROLE_HINTS = {
    "firewall": ("fw", "firewall", "fgt", "forti", "sophos", "paloalto", "pfsense", "utm"),
    "modem": ("modem", "router", "rtr", "cpe", "adsl", "vdsl", "gpon", "ont", "dsl"),
    "switch": ("sw", "switch", "swt"),
    "access-point": ("ap", "wifi", "wlan", "accesspoint"),
    "server": ("srv", "server", "sunucu", "nas"),
}

SEPARATORS = re.compile(r"[-_.\s]+")


def guess_role(host_name: str) -> str:
    tokens = [t.lower() for t in SEPARATORS.split(host_name) if t]
    for role, hints in ROLE_HINTS.items():
        for token in tokens:
            if token in hints:
                return role
    # Tam eşleşme yoksa alt dize olarak ara (ör. "ANKFW01").
    lowered = host_name.lower()
    for role, hints in ROLE_HINTS.items():
        if any(h in lowered for h in hints if len(h) > 3):
            return role
    return "?"


def guess_site_key(host_name: str) -> str:
    """Cihaz rolünü ve sıra numarasını atarak yurt anahtarını tahmin eder."""
    tokens = [t for t in SEPARATORS.split(host_name) if t]
    kept = []
    for token in tokens:
        low = token.lower()
        if any(low in hints for hints in ROLE_HINTS.values()):
            continue
        if re.fullmatch(r"\d{1,3}", token):  # sondaki sıra numarası
            continue
        kept.append(token)
    return "-".join(kept) if kept else host_name


def dump(client: ZabbixClient, config: dict[str, Any], sample_hosts: int = 3) -> str:
    """Envanter raporunu metin olarak üretir."""
    out: list[str] = []
    add = out.append

    add("=" * 78)
    add("ZABBIX ENVANTER DÖKÜMÜ")
    add(f"API sürümü: {client.version}")
    add("=" * 78)

    all_groups = client._rpc("hostgroup.get", {"output": ["groupid", "name"]})
    hosts = _hosts_with_templates(client, config["zabbix"]["host_groups"])

    # ---------------------------------------------------------------- gruplar
    add("")
    add("--- HOST GRUPLARI (Zabbix'teki tüm gruplar) " + "-" * 33)
    group_counts: Counter[str] = Counter()
    for host in hosts:
        for group in host.get("groups") or []:
            group_counts[group["name"]] += 1
    for group in sorted(all_groups, key=lambda g: g["name"]):
        marker = f"  [seçili kapsamda {group_counts[group['name']]} host]" if group_counts.get(group["name"]) else ""
        add(f"  {group['name']}{marker}")

    add("")
    add(f"--- KAPSAMDAKİ HOST SAYISI: {len(hosts)} " + "-" * 40)
    if not hosts:
        add("  Hiç host bulunamadı. config.yaml > zabbix.host_groups ayarını kontrol edin.")
        return "\n".join(out)

    # -------------------------------------------------------------- şablonlar
    add("")
    add("--- KULLANILAN ŞABLONLAR " + "-" * 52)
    template_counts: Counter[str] = Counter()
    for host in hosts:
        for template in host.get("parentTemplates") or []:
            template_counts[template["name"]] += 1
    for name, count in template_counts.most_common():
        add(f"  {count:4d} host  {name}")

    # ------------------------------------------------------------------ etiket
    add("")
    add("--- HOST ETİKETLERİ (tag) " + "-" * 51)
    tag_counts: Counter[str] = Counter()
    for host in hosts:
        for tag in host.get("tags") or []:
            tag_counts[f"{tag.get('tag')} = {tag.get('value')}"] += 1
    if tag_counts:
        for name, count in tag_counts.most_common(40):
            add(f"  {count:4d} host  {name}")
    else:
        add("  Hiç host etiketi tanımlanmamış.")

    # ------------------------------------------------- yurt / cihaz gruplaması
    add("")
    add("--- HOST ADLARI ve TAHMİNİ YURT/CİHAZ EŞLEMESİ " + "-" * 30)
    add("    (Tahmin sadece fikir vermek içindir; doğrusunu siz teyit edeceksiniz.)")
    add("")
    sites: dict[str, list[tuple[str, str]]] = {}
    for host in hosts:
        technical = host["host"]
        sites.setdefault(guess_site_key(technical), []).append(
            (technical, guess_role(technical))
        )
    add(f"    Tahmini yurt sayısı: {len(sites)}  ·  Yurt başına ortalama cihaz: "
        f"{len(hosts) / len(sites):.1f}")
    add("")
    for site_key in sorted(sites)[:60]:
        members = sites[site_key]
        add(f"  YURT? {site_key}   ({len(members)} cihaz)")
        for technical, role in members:
            add(f"        - {technical:<40} rol tahmini: {role}")
    if len(sites) > 60:
        add(f"  … ve {len(sites) - 60} yurt daha (çıktı kısaltıldı)")

    # -------------------------------------------------------------- item key'ler
    add("")
    add("--- ITEM KEY DAĞILIMI (tüm hostlar, normalleştirilmiş) " + "-" * 23)
    add("    [n] = köşeli parantez içindeki parametreler gizlendi")
    add("")
    items = client.get_items([h["hostid"] for h in hosts])
    key_counts: Counter[str] = Counter()
    for item in items:
        key_counts[re.sub(r"\[[^\]]*\]", "[…]", item["key_"])] += 1
    for key, count in key_counts.most_common(120):
        add(f"  {count:5d}x  {key}")
    if len(key_counts) > 120:
        add(f"  … ve {len(key_counts) - 120} farklı key daha")

    # --------------------------------------------------- örnek hostların detayı
    add("")
    add("--- ÖRNEK HOSTLARIN TAM ITEM LİSTESİ " + "-" * 40)
    items_by_host: dict[str, list[dict]] = {}
    for item in items:
        items_by_host.setdefault(item["hostid"], []).append(item)

    for host in hosts[:sample_hosts]:
        group_names = ", ".join(g["name"] for g in host.get("groups") or []) or "—"
        tag_list = ", ".join(
            f"{t.get('tag')}={t.get('value')}" for t in host.get("tags") or []
        ) or "—"
        template_names = ", ".join(
            t["name"] for t in host.get("parentTemplates") or []
        ) or "—"

        add("")
        add(f"  ### {host.get('name') or host['host']}  (teknik ad: {host['host']})")
        add(f"      IP/DNS   : {host.get('address') or '—'}")
        add(f"      Gruplar  : {group_names}")
        add(f"      Etiketler: {tag_list}")
        add(f"      Şablonlar: {template_names}")
        add("      Item'lar:")
        for item in sorted(items_by_host.get(host["hostid"], []), key=lambda i: i["key_"]):
            units = f" [{item['units']}]" if item.get("units") else ""
            add(f"        {item['key_']:<48} {item['name']}{units}")

    add("")
    add("=" * 78)
    add("Bu çıktıyı olduğu gibi paylaşabilirsiniz — parola veya token içermez.")
    add("=" * 78)
    return "\n".join(out)


def _hosts_with_templates(client: ZabbixClient, host_groups: list[str]) -> list[dict[str, Any]]:
    """host.get, ayrıca bağlı şablonlarla birlikte."""
    params: dict[str, Any] = {
        "output": ["hostid", "host", "name", "status"],
        "selectTags": ["tag", "value"],
        "selectParentTemplates": ["name"],
        "selectInterfaces": ["ip", "dns", "useip"],
        "filter": {"status": 0},
    }
    params["selectHostGroups" if client._version_at_least(6, 2) else "selectGroups"] = ["name"]

    groups = [g for g in (host_groups or []) if g]
    if groups:
        group_ids = [g["groupid"] for g in client.get_host_groups(groups)]
        if not group_ids:
            return []
        params["groupids"] = group_ids

    hosts = client._rpc("host.get", params)
    for host in hosts:
        host["groups"] = host.pop("hostgroups", None) or host.get("groups") or []
        iface = (host.get("interfaces") or [{}])[0]
        host["address"] = (
            iface.get("ip") if iface.get("useip") == "1" else iface.get("dns")
        ) or ""
    return hosts
