"""Dashboard, e-posta ve raporlarda ortak kullanılan biçimlendirme yardımcıları."""

from __future__ import annotations

import datetime as dt
import html

SEVERITY_LABEL = {
    "ok": "Normal",
    "info": "Bilgi",
    "warning": "Uyarı",
    "critical": "Kritik",
}

SEVERITY_COLOR = {
    "ok": "#1a7f4e",
    "info": "#2563a8",
    "warning": "#b06a00",
    "critical": "#b3261e",
}

SEVERITY_BG = {
    "ok": "#e6f4ec",
    "info": "#e6eef8",
    "warning": "#fdf0dd",
    "critical": "#fbe6e4",
}

# E-postalarda harici CSS çalışmadığı için stiller satır içi verilir.
BASE_FONT = "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def fmt_bps(bps: float | None) -> str:
    if bps is None:
        return "—"
    for unit, factor in (("Gbps", 1e9), ("Mbps", 1e6), ("Kbps", 1e3)):
        if bps >= factor:
            return f"{bps / factor:.1f} {unit}"
    return f"{bps:.0f} bps"


def fmt_pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"%{value:.{digits}f}"


def fmt_ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f} ms"


def fmt_duration(seconds: int | float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} sn"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} dk"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} sa {minutes} dk"
    days, hours = divmod(hours, 24)
    return f"{days} gün {hours} sa"


def fmt_time(ts: int | float | None) -> str:
    if not ts:
        return "—"
    return dt.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def severity_badge(severity: str) -> str:
    color = SEVERITY_COLOR.get(severity, "#555")
    background = SEVERITY_BG.get(severity, "#eee")
    label = SEVERITY_LABEL.get(severity, severity)
    return (
        f'<span style="display:inline-block;padding:2px 9px;border-radius:11px;'
        f"font-size:12px;font-weight:600;color:{color};background:{background};"
        f'white-space:nowrap">{esc(label)}</span>'
    )
