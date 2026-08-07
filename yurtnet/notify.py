"""E-posta bildirimleri.

Gürültüyü kısmak için üç mekanizma var:
  1. min_severity — belirlenen seviyenin altındaki bulgular mail edilmez,
  2. cooldown    — aynı arıza için belirlenen süre dolmadan tekrar mail gitmez,
  3. gruplama    — bir turdaki tüm arızalar tek bir mailde toplanır.
"""

from __future__ import annotations

import logging
import smtplib
import time
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from .render import (
    BASE_FONT,
    esc,
    fmt_duration,
    fmt_time,
    severity_badge,
)
from .store import Incident

log = logging.getLogger(__name__)

SEVERITY_ORDER = {"info": 1, "warning": 2, "critical": 3}


def pano_adresi(config: dict[str, Any]) -> str:
    """Maile konacak dashboard adresi.

    `bind` değeri buraya yazılamaz: 127.0.0.1 "bu makine" demektir ve mailin
    açıldığı telefonda/başka bilgisayarda hiçbir şeye karşılık gelmez.
    Erişilebilir adres `dashboard.public_url` ile açıkça verilir.
    """
    dash = config.get("dashboard") or {}
    if not dash.get("enabled"):
        return ""
    url = (dash.get("public_url") or "").strip()
    if url:
        return url.rstrip("/") + "/"
    bind = dash.get("bind", "")
    if bind in ("0.0.0.0", "::", ""):
        return ""  # dışarıdan hangi adresle görüleceği bilinmiyor
    return f"http://{bind}:{dash.get('port', 8787)}/"


def send_mail(
    config: dict[str, Any],
    subject: str,
    html_body: str,
    recipients: list[str] | None = None,
    ekler: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """Tek bir mail gönderir. Başarı durumunu döner (hata fırlatmaz).

    `ekler`: (dosya adı, içerik, MIME alt tipi) üçlüleri. Aylık rapor PDF'i
    ek olarak gidiyor — yönetici maili açtığında indirmek için panoya girmek
    zorunda kalmasın.
    """
    mail_config = config["email"]
    if not mail_config.get("enabled"):
        log.info("E-posta kapalı, gönderilmedi: %s", subject)
        return False

    to_addresses = recipients or mail_config["recipients"]
    if not to_addresses:
        log.warning("Alıcı yok, mail gönderilmedi: %s", subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr(("Yurt İnternet İzleme", mail_config["sender"]))
    message["To"] = ", ".join(to_addresses)
    message.set_content(
        "Bu mesaj HTML biçimindedir. HTML görüntüleyebilen bir istemci ile açın."
    )
    message.add_alternative(html_body, subtype="html")
    for ad, icerik, alt_tip in ekler or []:
        message.add_attachment(
            icerik, maintype="application", subtype=alt_tip, filename=ad
        )

    try:
        if mail_config.get("use_ssl"):
            server = smtplib.SMTP_SSL(
                mail_config["smtp_host"], mail_config["smtp_port"], timeout=30
            )
        else:
            server = smtplib.SMTP(mail_config["smtp_host"], mail_config["smtp_port"], timeout=30)
        with server:
            if mail_config.get("use_tls"):
                server.starttls()
            if mail_config.get("username"):
                server.login(mail_config["username"], mail_config["password"])
            server.send_message(message)
    except Exception as exc:
        log.error("Mail gönderilemedi (%s): %s", subject, exc)
        return False

    log.info("Mail gönderildi: %s -> %s", subject, ", ".join(to_addresses))
    return True


def select_notifiable(incidents: list[Incident], config: dict[str, Any], now: int | None = None) -> list[Incident]:
    """Seviye, süre ve soğuma filtrelerinden geçen arızaları seçer.

    Süre şartı önemli: bir arıza kaydı açıldığı anda mail atmak, iki dakika
    sonra kendiliğinden düzelecek bir dalgalanma için de telefon çaldırır.
    Sorunun gerçekten kalıcı olduğunu görmek için bir süre beklenir.
    """
    now = now or int(time.time())
    mail_config = config["email"]
    minimum = SEVERITY_ORDER.get(mail_config["min_severity"], 2)
    cooldown = mail_config["alert_cooldown_minutes"] * 60
    min_sure = int(mail_config.get("min_duration_minutes", 5)) * 60

    selected = []
    for incident in incidents:
        if SEVERITY_ORDER.get(incident.severity, 0) < minimum:
            continue
        # Kayıt açıldığından beri yeterince zaman geçmiş mi?
        if (now - incident.started_at) < min_sure:
            continue
        if incident.notified_at and (now - incident.notified_at) < cooldown:
            continue
        selected.append(incident)
    return selected


def suppress_covered_by_region(incidents: list[Incident]) -> list[Incident]:
    """Bölgesel kesinti bildirimi varken o bölgedeki tekil 'kopuk' mailleri bastır.

    30 yurdun her biri için ayrı mail yerine tek bölgesel uyarı gitsin diye.
    """
    regions_down = {i.region for i in incidents if i.code == "REGIONAL_OUTAGE"}
    if not regions_down:
        return incidents
    return [
        i
        for i in incidents
        if i.code == "REGIONAL_OUTAGE"
        or i.region not in regions_down
        or i.code not in ("HOST_DOWN", "NO_DATA")
    ]


def build_alert_subject(incidents: list[Incident]) -> str:
    critical = [i for i in incidents if i.severity == "critical"]
    prefix = "[KRİTİK]" if critical else "[UYARI]"
    lead = incidents[0]
    where = lead.name or lead.region or "?"
    if len(incidents) == 1:
        return f"{prefix} {where} — {lead.title}"
    return f"{prefix} {len(incidents)} arıza — {where} ve diğerleri"


def render_alert_email(incidents: list[Incident], config: dict[str, Any]) -> str:
    cards = "\n".join(_incident_card(i) for i in incidents)
    dashboard = config["dashboard"]
    link = ""
    adres = pano_adresi(config)
    if dashboard.get("enabled") and adres:
        link = (
            f'<p style="{BASE_FONT}font-size:14px;margin-top:20px">'
            f'<a href="{esc(adres)}" style="background:#2a78d6;color:#fff;text-decoration:none;'
            f'padding:11px 20px;border-radius:7px;display:inline-block;font-weight:600">'
            f"Canlı tabloyu aç</a></p>"
            f'<p style="{BASE_FONT}font-size:12px;color:#888;margin-top:8px">{esc(adres)}</p>'
        )
    return f"""
<div style="{BASE_FONT}background:#f5f6f8;padding:20px">
  <div style="max-width:720px;margin:0 auto">
    <h2 style="margin:0 0 4px;font-size:19px;color:#1a1a1a">Yurt İnternet İzleme — Arıza Bildirimi</h2>
    <p style="margin:0 0 16px;font-size:13px;color:#666">{esc(fmt_time(time.time()))} · {len(incidents)} aktif bulgu</p>
    {cards}
    {link}
  </div>
</div>
"""


def _incident_card(incident: Incident) -> str:
    where = incident.name or incident.region or "—"
    remote = (
        '<span style="color:#1a7f4e">Uzaktan çözülebilir</span>'
        if incident.remote_fixable
        else '<span style="color:#b3261e">Muhtemelen yerinde müdahale gerekir</span>'
    )
    return f"""
<div style="background:#fff;border:1px solid #e2e4e8;border-left:4px solid {_color(incident.severity)};
            border-radius:6px;padding:14px 16px;margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <strong style="font-size:15px;color:#1a1a1a">{esc(where)}</strong> {severity_badge(incident.severity)}
  </div>
  <div style="font-size:14px;color:#1a1a1a;margin-top:6px"><strong>{esc(incident.title)}</strong></div>
  <div style="font-size:12px;color:#777;margin-top:2px">
    Bölge: {esc(incident.region or '—')} · Başlangıç: {esc(fmt_time(incident.started_at))}
    · Süre: {esc(fmt_duration(incident.duration_seconds))}
  </div>
  <p style="font-size:13px;color:#333;margin:10px 0 6px;line-height:1.5">
    <strong>Muhtemel sebep:</strong> {esc(incident.detail)}
  </p>
  <p style="font-size:13px;color:#333;margin:0 0 6px;line-height:1.5">
    <strong>Önerilen aksiyon:</strong> {esc(incident.action)}
  </p>
  <div style="font-size:12px">{remote}</div>
</div>
"""


def render_recovery_email(incidents: list[Incident]) -> str:
    rows = "\n".join(
        f"""<tr>
  <td style="padding:8px 10px;border-bottom:1px solid #eee;font-size:13px">{esc(i.name or i.region)}</td>
  <td style="padding:8px 10px;border-bottom:1px solid #eee;font-size:13px;color:#666">{esc(i.title)}</td>
  <td style="padding:8px 10px;border-bottom:1px solid #eee;font-size:13px">{esc(fmt_duration(i.duration_seconds))}</td>
</tr>"""
        for i in incidents
    )
    return f"""
<div style="{BASE_FONT}background:#f5f6f8;padding:20px">
  <div style="max-width:640px;margin:0 auto;background:#fff;border:1px solid #e2e4e8;border-radius:6px;padding:16px">
    <h2 style="margin:0 0 12px;font-size:17px;color:#1a7f4e">Düzeldi — {len(incidents)} arıza kapandı</h2>
    <table style="width:100%;border-collapse:collapse">
      <tr style="text-align:left;color:#666;font-size:12px">
        <th style="padding:6px 10px">Yurt</th><th style="padding:6px 10px">Arıza</th><th style="padding:6px 10px">Süre</th>
      </tr>
      {rows}
    </table>
  </div>
</div>
"""


def _color(severity: str) -> str:
    from .render import SEVERITY_COLOR

    return SEVERITY_COLOR.get(severity, "#999")
