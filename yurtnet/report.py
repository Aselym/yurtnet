"""Haftalık özet raporu.

Amaç operasyonel değil yönetsel: hangi yurt sürekli sorun çıkarıyor, kesintiler
nerede yoğunlaşıyor, hangi arıza tipi baskın. Kalıcı çözüm kararları buradan çıkar.
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path
from typing import Any

from .render import BASE_FONT, esc, fmt_duration, fmt_ms, fmt_pct, fmt_time
from .store import KESINTI_KODLARI, Store, ariza_suresi

CODE_LABEL = {
    "NO_DATA": "Veri gelmiyor",
    "HOST_DOWN": "Bağlantı kopuk",
    "WAN_SILENT": "WAN sessiz (trafik yok)",
    "WAN_IFACE_DOWN": "İnternet bacağı kapalı",
    "REBOOTED": "Cihaz yeniden başladı",
    "NO_IF_DATA": "Trafik verisi yok (SNMP)",
    "PACKET_LOSS": "Paket kaybı",
    "HIGH_LATENCY": "Yüksek gecikme",
    "SATURATION": "Hat doluluğu",
    "IF_ERRORS": "Arayüz hataları",
    "HIGH_CPU": "Yüksek CPU",
    "HIGH_MEMORY": "Yüksek bellek",
    "FLAPPING": "Hat flapping",
    "REGIONAL_OUTAGE": "Bölgesel kesinti",
    "STALE_DATA": "İzleme verisi bayat",
}

TH = 'style="text-align:left;padding:7px 10px;font-size:11px;color:#666;text-transform:uppercase;border-bottom:2px solid #e2e4e8"'
TD = 'style="padding:7px 10px;font-size:13px;border-bottom:1px solid #eee"'


def build(store: Store, config: dict[str, Any], now: int | None = None) -> tuple[str, str]:
    """(konu, html) döner."""
    now = now or int(time.time())
    since = now - 7 * 86400
    stats = store.weekly_stats(since, now)

    hosts = stats["hosts"]
    incidents = stats["incidents"]
    problem_hosts = [h for h in hosts if h["down"] > 0 or (h["avg_loss"] or 0) > 0.5]
    # Yalnızca gerçekten sorun yaşayanlar listelenir; kusursuz yurtlarla tabloyu
    # doldurmak "en kötü 10" başlığını anlamsızlaştırırdı.
    worst = sorted(problem_hosts, key=lambda h: (h["uptime_pct"], -(h["avg_loss"] or 0)))[:10]
    busiest = sorted(hosts, key=lambda h: -(h["peak_util"] or 0))[:10]

    fleet_uptime = (
        sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    )
    total_downtime = sum(
        ariza_suresi(i, now)
        for i in incidents
        if i.code in KESINTI_KODLARI
    )

    subject = (
        f"Haftalık Yurt İnternet Raporu — {fmt_time(since)[:10]} / {fmt_time(now)[:10]} "
        f"· {len(incidents)} arıza"
    )

    html = f"""
<div style="{BASE_FONT}background:#f5f6f8;padding:22px">
 <div style="max-width:820px;margin:0 auto">
  <h2 style="margin:0 0 2px;font-size:20px">Haftalık Yurt İnternet Raporu</h2>
  <p style="margin:0 0 18px;color:#666;font-size:13px">
    {esc(fmt_time(since))} – {esc(fmt_time(now))} · {len(hosts)} yurt izlendi
  </p>

  {_kpi_row([
      ("Ortalama erişilebilirlik", fmt_pct(fleet_uptime, 2)),
      ("Toplam kesinti süresi", fmt_duration(total_downtime)),
      ("Açılan arıza", str(len(incidents))),
      ("Sorun yaşayan yurt", f"{len(problem_hosts)} / {len(hosts)}"),
  ])}

  {_section("En çok sorun yaşayan 10 yurt", _worst_table(worst))}
  {_section("Hat doluluğu en yüksek 10 yurt", _busiest_table(busiest))}
  {_section("Arıza tiplerine göre dağılım", _code_table(stats["by_code"]))}
  {_section("Bölgelere göre arıza sayısı", _region_table(stats["by_region"]))}
  {_section("Haftanın en uzun 10 kesintisi", _incident_table(incidents, now))}

  <p style="color:#888;font-size:11.5px;margin-top:20px">
    Bu rapor yurtnet tarafından otomatik üretildi. Erişilebilirlik,
    {config['poll']['check_interval_minutes']} dakikalık kontrol turlarının başarı oranıdır.
  </p>
 </div>
</div>
"""
    return subject, html


def build_text(store: Store, config: dict[str, Any], now: int | None = None) -> str:
    """Raporun düz metin (Markdown) sürümü.

    HTML sürümü insan gözü için; bu sürüm kopyalanıp bir sohbete yapıştırılmak
    veya arşivlenmek için. Aynı verilerden üretilir, sadece biçimi sadedir.
    """
    now = now or int(time.time())
    since = now - 7 * 86400
    stats = store.weekly_stats(since, now)
    hosts = stats["hosts"]
    incidents = stats["incidents"]

    fleet_uptime = sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    total_downtime = sum(
        ariza_suresi(i, now)
        for i in incidents
        if i.code in KESINTI_KODLARI
    )
    problem_hosts = [h for h in hosts if h["down"] > 0 or (h["avg_loss"] or 0) > 0.5]

    satirlar: list[str] = []
    add = satirlar.append

    add(f"# Haftalık Yurt İnternet Raporu")
    add(f"{fmt_time(since)} – {fmt_time(now)} · {len(hosts)} yurt")
    add("")
    add(f"- Ortalama erişilebilirlik: {fmt_pct(fleet_uptime, 2)}")
    add(f"- Toplam kesinti süresi: {fmt_duration(total_downtime)}")
    add(f"- Açılan arıza: {len(incidents)}")
    add(f"- Sorun yaşayan yurt: {len(problem_hosts)} / {len(hosts)}")
    add("")

    worst = sorted(problem_hosts, key=lambda h: (h["uptime_pct"], -(h["avg_loss"] or 0)))[:10]
    add("## En çok sorun yaşayan yurtlar")
    add("")
    if worst:
        add("| Yurt | Bölge | Erişilebilirlik | Başarısız | Ort. gecikme | Ort. kayıp |")
        add("|---|---|---|---|---|---|")
        for h in worst:
            add(
                f"| {h['name']} | {h['region']} | {fmt_pct(h['uptime_pct'], 2)} "
                f"| {h['down']}/{h['checks']} | {fmt_ms(h['avg_latency'])} | {fmt_pct(h['avg_loss'])} |"
            )
    else:
        add("Bu hafta hiçbir yurtta kesinti veya kayda değer paket kaybı yaşanmadı.")
    add("")

    busiest = [h for h in sorted(hosts, key=lambda h: -(h["peak_util"] or 0))[:10] if h["peak_util"]]
    if busiest:
        add("## Hat doluluğu en yüksek yurtlar")
        add("")
        add("| Yurt | Tepe doluluk | Ortalama |")
        add("|---|---|---|")
        for h in busiest:
            add(f"| {h['name']} | {fmt_pct(h['peak_util'], 0)} | {fmt_pct(h['avg_util'], 0)} |")
        add("")

    if stats["by_code"]:
        add("## Arıza tipleri")
        add("")
        add("| Tip | Adet | Toplam süre |")
        add("|---|---|---|")
        for row in stats["by_code"]:
            add(
                f"| {CODE_LABEL.get(row['code'], row['code'])} | {row['n']} "
                f"| {fmt_duration(row['total_seconds'])} |"
            )
        add("")

    if stats["by_region"]:
        add("## Bölgelere göre arıza")
        add("")
        for row in stats["by_region"]:
            add(f"- {row['region'] or '—'}: {row['n']}")
        add("")

    uzun = sorted(incidents, key=lambda i: -(ariza_suresi(i, now)))[:10]
    if uzun:
        add("## En uzun kesintiler")
        add("")
        add("| Yurt | Arıza | Başlangıç | Süre | Durum |")
        add("|---|---|---|---|---|")
        for i in uzun:
            add(
                f"| {i.name or i.region or '—'} | {CODE_LABEL.get(i.code, i.code)} "
                f"| {fmt_time(i.started_at)} | {fmt_duration(ariza_suresi(i, now))} "
                f"| {'Açık' if i.ended_at is None else 'Kapandı'} |"
            )
        add("")

    add("---")
    add(
        f"yurtnet tarafından otomatik üretildi. Erişilebilirlik, "
        f"{config['poll']['check_interval_minutes']} dakikalık kontrol turlarının başarı oranıdır."
    )
    return "\n".join(satirlar)


def save(store: Store, config: dict[str, Any], now: int | None = None) -> tuple[Path, Path]:
    """Raporu HTML ve Markdown olarak diske yazar; (html_yolu, md_yolu) döner.

    E-posta ayarlansa da ayarlanmasa da rapor birikir: dashboard üzerinden
    açılabilir ve arşiv olarak kalır.
    """
    now = now or int(time.time())
    _, html = build(store, config, now)
    text = build_text(store, config, now)

    klasor = Path(config["_base_dir"]) / "raporlar"
    klasor.mkdir(exist_ok=True)
    damga = dt.datetime.fromtimestamp(now).strftime("%Y-%m-%d")

    html_yolu = klasor / f"{damga}-haftalik.html"
    md_yolu = klasor / f"{damga}-haftalik.md"
    html_yolu.write_text(html, encoding="utf-8")
    md_yolu.write_text(text, encoding="utf-8")

    # Dashboard'dan sabit bir adresle erişilebilsin diye son rapor kopyalanır.
    (klasor / "son-rapor.html").write_text(html, encoding="utf-8")
    (klasor / "son-rapor.md").write_text(text, encoding="utf-8")
    return html_yolu, md_yolu


def _kpi_row(items: list[tuple[str, str]]) -> str:
    cells = "".join(
        f"""<td style="background:#fff;border:1px solid #e2e4e8;border-radius:8px;padding:12px 14px;width:25%">
              <div style="font-size:20px;font-weight:700;color:#1a1a1a">{esc(value)}</div>
              <div style="font-size:11px;color:#777;text-transform:uppercase">{esc(label)}</div>
            </td><td style="width:8px"></td>"""
        for label, value in items
    )
    return f'<table style="width:100%;border-collapse:separate;border-spacing:0"><tr>{cells}</tr></table>'


def _section(title: str, body: str) -> str:
    return f"""
<div style="background:#fff;border:1px solid #e2e4e8;border-radius:8px;padding:14px 16px;margin-top:14px">
  <h3 style="margin:0 0 10px;font-size:14px;color:#1a1a1a">{esc(title)}</h3>
  {body}
</div>"""


def _empty(message: str) -> str:
    return f'<p style="color:#888;font-size:13px;margin:0">{esc(message)}</p>'


def _worst_table(hosts: list[dict]) -> str:
    if not hosts:
        return _empty("Veri yok.")
    rows = "".join(
        f"""<tr>
          <td {TD}>{esc(h['name'])}</td>
          <td {TD}>{esc(h['region'])}</td>
          <td {TD}><strong style="color:{'#b3261e' if h['uptime_pct'] < 99 else '#1a7f4e'}">
            {esc(fmt_pct(h['uptime_pct'], 2))}</strong></td>
          <td {TD}>{esc(h['down'])} / {esc(h['checks'])}</td>
          <td {TD}>{esc(fmt_ms(h['avg_latency']))}</td>
          <td {TD}>{esc(fmt_pct(h['avg_loss']))}</td>
        </tr>"""
        for h in hosts
    )
    return f"""<table style="width:100%;border-collapse:collapse">
      <tr><th {TH}>Yurt</th><th {TH}>Bölge</th><th {TH}>Erişilebilirlik</th>
          <th {TH}>Başarısız kontrol</th><th {TH}>Ort. gecikme</th><th {TH}>Ort. kayıp</th></tr>
      {rows}</table>"""


def _busiest_table(hosts: list[dict]) -> str:
    hosts = [h for h in hosts if h["peak_util"] is not None]
    if not hosts:
        return _empty("Trafik verisi toplanmamış — item_keys ayarlarını kontrol edin.")
    rows = "".join(
        f"""<tr>
          <td {TD}>{esc(h['name'])}</td><td {TD}>{esc(h['region'])}</td>
          <td {TD}><strong>{esc(fmt_pct(h['peak_util'], 0))}</strong></td>
          <td {TD}>{esc(fmt_pct(h['avg_util'], 0))}</td>
        </tr>"""
        for h in hosts
    )
    return f"""<table style="width:100%;border-collapse:collapse">
      <tr><th {TH}>Yurt</th><th {TH}>Bölge</th><th {TH}>Tepe doluluk</th><th {TH}>Ortalama doluluk</th></tr>
      {rows}</table>
      <p style="color:#888;font-size:12px;margin:8px 0 0">
        Tepe doluluğu sürekli %80 üzerinde olan yurtlar için hat yükseltmesi değerlendirilmelidir.</p>"""


def _code_table(by_code: list[dict]) -> str:
    if not by_code:
        return _empty("Bu hafta hiç arıza kaydı açılmadı.")
    rows = "".join(
        f"""<tr><td {TD}>{esc(CODE_LABEL.get(row['code'], row['code']))}</td>
              <td {TD}>{esc(row['n'])}</td>
              <td {TD}>{esc(fmt_duration(row['total_seconds']))}</td></tr>"""
        for row in by_code
    )
    return f"""<table style="width:100%;border-collapse:collapse">
      <tr><th {TH}>Arıza tipi</th><th {TH}>Adet</th><th {TH}>Toplam süre</th></tr>{rows}</table>"""


def _region_table(by_region: list[dict]) -> str:
    if not by_region:
        return _empty("Bu hafta hiç arıza kaydı açılmadı.")
    total = sum(r["n"] for r in by_region) or 1
    rows = "".join(
        f"""<tr><td {TD}>{esc(row['region'] or '—')}</td><td {TD}>{esc(row['n'])}</td>
              <td {TD}>{esc(fmt_pct(row['n'] / total * 100, 0))}</td></tr>"""
        for row in by_region
    )
    return f"""<table style="width:100%;border-collapse:collapse">
      <tr><th {TH}>Bölge</th><th {TH}>Arıza</th><th {TH}>Pay</th></tr>{rows}</table>"""


def _incident_table(incidents: list, now: int) -> str:
    outages = sorted(
        incidents, key=lambda i: -(ariza_suresi(i, now))
    )[:10]
    if not outages:
        return _empty("Bu hafta hiç arıza kaydı açılmadı.")
    rows = "".join(
        f"""<tr>
          <td {TD}>{esc(i.name or i.region or '—')}</td>
          <td {TD}>{esc(CODE_LABEL.get(i.code, i.code))}</td>
          <td {TD}>{esc(fmt_time(i.started_at))}</td>
          <td {TD}><strong>{esc(fmt_duration(ariza_suresi(i, now)))}</strong></td>
          <td {TD}>{'Açık' if i.ended_at is None else 'Kapandı'}</td>
        </tr>"""
        for i in outages
    )
    return f"""<table style="width:100%;border-collapse:collapse">
      <tr><th {TH}>Yurt</th><th {TH}>Arıza</th><th {TH}>Başlangıç</th>
          <th {TH}>Süre</th><th {TH}>Durum</th></tr>{rows}</table>"""
