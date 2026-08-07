"""Uygulamanın giriş noktası: zamanlayıcı, kontrol turu ve CLI."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import signal
import sys
import time
from typing import Any

from pathlib import Path

from . import (
    collect,
    dashboard,
    ekran,
    diagnose,
    inventory,
    notify,
    report,
    reports_html,
)
from .brand import LOGO_DATA_URI
from .config import ConfigError, load
from .store import KESINTI_KODLARI, Store, ariza_suresi
from .zabbix import ZabbixClient, ZabbixError

log = logging.getLogger("yurtnet")

WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}

_stop = False


def _handle_signal(*_args: object) -> None:
    global _stop
    _stop = True
    log.info("Kapatma sinyali alındı, mevcut tur bitince duracak.")


def run_cycle(config: dict[str, Any], store: Store) -> dict[str, Any]:
    """Tek bir kontrol turu: veri topla → tanı koy → kaydet → bildir → tabloyu güncelle."""
    started = time.time()

    # Hat kapasiteleri bilinmiyorsa geçmiş trafikten öğrenilenler kullanılır.
    capacity_lookup = None
    if config["bandwidth"].get("mode") == "learned":
        learned = store.learned_capacities(
            config["bandwidth"].get("learn_min_days", 7),
            config["bandwidth"].get("learn_min_samples", 500),
        )
        capacity_lookup = learned.get

    with ZabbixClient(config["zabbix"]) as client:
        snapshots = collect.collect(client, config, capacity_lookup)

    if not snapshots:
        log.warning("Bu turda hiç yurt verisi alınamadı.")
        return {"hosts": 0}

    planned = _planli_temizle(store, snapshots)
    # Arayüz hata sayacı karşılaştırması için önceki değerler, YENİ ölçüm
    # kaydedilmeden önce okunmalı; sonra okunursa kendisiyle karşılaştırılır.
    onceki_hatalar = store.onceki_if_errors()
    store.record(snapshots, set(planned))
    _son_snapshotlar[:] = snapshots

    findings_by_host, regional = _tani_koy(
        config, store, snapshots, planned, onceki_hatalar
    )

    all_findings = [f for fs in findings_by_host.values() for f in fs] + regional
    # Bilinçli kapatma arıza kaydı üretmez; tabloda bilgi olarak görünür.
    kayda_deger = [f for f in all_findings if f.code != "PLANNED_DOWN"]
    # Tabloda her şey anında görünür; arıza kaydı ve mail için teyit beklenir.
    opened, resolved = store.sync_incidents(
        _confirmed(kayda_deger, config, store.acik_dedup_keys())
    )

    _notify(config, store, opened, resolved)
    _refresh_dashboard(config, snapshots, findings_by_host, regional, store)
    _refresh_reports(config, store)

    critical = sum(1 for f in all_findings if f.severity == "critical")
    log.info(
        "Tur bitti: %d yurt, %d bulgu (%d kritik), %d kapanan — %.1f sn",
        len(snapshots), len(all_findings), critical, len(resolved), time.time() - started,
    )
    return {
        "hosts": len(snapshots),
        "findings": len(all_findings),
        "critical": critical,
        "resolved": len(resolved),
    }


# Son turun ölçümleri: "planlı kapalı" düğmesine basıldığında tabloyu
# bir sonraki turu beklemeden yeniden çizebilmek için tutulur.
_son_snapshotlar: list = []


def _planli_temizle(store: Store, snapshots: list) -> dict[str, dict]:
    """Planlı kapalı listesini okur, geri gelen yurtların işaretini kaldırır.

    Unutulan bir işaret sessizce tehlikeli olurdu: yazın "kapalı" işaretlenen
    yurtta sonbaharda gerçek bir arıza çıksa gizlenirdi. Cihaz ping'e cevap
    vermeye başladığı an işaret otomatik düşer.
    """
    planned = store.planned_down()
    if not planned:
        return {}
    for snap in snapshots:
        if snap.hostid in planned and snap.reachable is True:
            store.clear_planned(snap.hostid)
            planned.pop(snap.hostid, None)
            log.info(
                "%s yeniden çevrimiçi — 'bilinçli kapalı' işareti kaldırıldı.", snap.name
            )
    return planned


def _tani_koy(
    config, store: Store, snapshots: list, planned: dict[str, dict],
    onceki_hatalar: dict[str, float] | None = None,
):
    """Ölçümlerden bulguları üretir. Düğmeye basıldığında da yeniden çağrılır."""
    ctx = {
        "check_interval_seconds": config["poll"]["check_interval_minutes"] * 60,
        "planned": planned,
        "onceki_if_errors": onceki_hatalar or {},
    }
    findings_by_host: dict[str, list[diagnose.Finding]] = {}
    for snap in snapshots:
        findings = diagnose.diagnose_host(snap, config, ctx)
        flap = diagnose.detect_flapping(snap, store.transitions_last_hour(snap.hostid), config)
        if flap and not any(f.code == "PLANNED_DOWN" for f in findings):
            findings.insert(0, flap)
        findings_by_host[snap.hostid] = findings
    regional = diagnose.detect_regional_outage(snapshots, findings_by_host, config)
    return findings_by_host, regional


def _ekran_yaz(config, snapshots, findings_by_host, regional, store=None) -> None:
    """Duvara asılan televizyon sayfasını yazar.

    Hata yutulur: ekran modu tali bir çıktı, üretilememesi izlemeyi ve
    panoyu durdurmamalı.
    """
    try:
        html = ekran.render(snapshots, findings_by_host, regional, config, store)
        klasor = Path(config["dashboard"]["output_file"]).parent
        dashboard.write(html, str(klasor / dashboard.EKRAN_DOSYA))
    except Exception:
        log.exception("Ekran sayfası üretilemedi — izleme etkilenmedi.")


def yeniden_ciz(config, store: Store) -> bool:
    """Planlı kapalı işareti değişince tabloyu hemen günceller.

    Bir sonraki tur beklenirse kullanıcı düğmeye basıp hiçbir şey olmamış gibi
    görür; bu da düğmenin çalışmadığı izlenimi verir.
    """
    if not _son_snapshotlar:
        return False
    planned = store.planned_down()
    findings_by_host, regional = _tani_koy(config, store, _son_snapshotlar, planned)
    html = dashboard.render(_son_snapshotlar, findings_by_host, regional, config)
    dashboard.write(html, config["dashboard"]["output_file"])
    _ekran_yaz(config, _son_snapshotlar, findings_by_host, regional, store)
    return True


# Bulgunun arka arkaya kaç turdur görüldüğü: dedup_key -> sayaç
_ardisik: dict[str, int] = {}


def _confirmed(
    findings: list[diagnose.Finding], config, zaten_acik: set[str] | None = None
) -> list[diagnose.Finding]:
    """Yalnızca yeterli tur boyunca süren bulguları arıza saymak için filtreler.

    Dakikada bir kontrol edildiğinde tek bir anlık dalgalanma (trafiğin bir
    dakikalığına düşmesi, gecikmenin bir kez sıçraması) da bulgu üretir.
    Teyit beklenmezse bunların her biri ayrı bir arıza kaydı ve maili olur;
    gerçek arızalar bu gürültünün içinde kaybolur.
    """
    gereken = max(1, int(config["thresholds"].get("confirm_cycles", 2)))
    if gereken == 1:
        return findings

    aktif = {f.dedup_key for f in findings}
    for key in list(_ardisik):
        if key not in aktif:
            del _ardisik[key]  # kesildi, sayaç sıfırlanır

    zaten_acik = zaten_acik or set()
    teyitli = []
    for finding in findings:
        _ardisik[finding.dedup_key] = _ardisik.get(finding.dedup_key, 0) + 1
        # Zaten açık bir arıza yeniden teyit beklemez. Sayaç bellekte tutulduğu
        # için uygulama yeniden başladığında sıfırlanır; bu kontrol olmadan
        # açık kayıtlar her başlatmada kapanıp yeniden açılır ve sayı şişer.
        if _ardisik[finding.dedup_key] >= gereken or finding.dedup_key in zaten_acik:
            teyitli.append(finding)
    return teyitli


def _notify(config, store: Store, opened, resolved) -> None:
    candidates = notify.select_notifiable(opened, config)
    candidates = notify.suppress_covered_by_region(candidates)
    if candidates:
        candidates.sort(key=lambda i: (i.severity != "critical", i.name or ""))
        subject = notify.build_alert_subject(candidates)
        body = notify.render_alert_email(candidates, config)
        if notify.send_mail(config, subject, body):
            store.mark_notified([i.id for i in candidates])

    if resolved and config["email"].get("send_recovery"):
        # Sadece daha önce mail atılmış arızalar için "düzeldi" bilgisi gönderilir.
        announced = [i for i in resolved if i.notified_at]
        if announced:
            notify.send_mail(
                config,
                f"[DÜZELDİ] {len(announced)} arıza kapandı",
                notify.render_recovery_email(announced),
            )


_last_dashboard = 0.0


def _refresh_dashboard(config, snapshots, findings_by_host, regional, store=None) -> None:
    global _last_dashboard
    if not config["dashboard"].get("enabled"):
        return
    interval = config["poll"]["dashboard_refresh_minutes"] * 60
    now = time.time()
    if _last_dashboard and (now - _last_dashboard) < interval:
        return
    html = dashboard.render(snapshots, findings_by_host, regional, config)
    dashboard.write(html, config["dashboard"]["output_file"])
    _ekran_yaz(config, snapshots, findings_by_host, regional, store)
    _last_dashboard = now
    log.debug("Dashboard güncellendi: %s", config["dashboard"]["output_file"])


_last_reports = 0.0


def _refresh_reports(config: dict[str, Any], store: Store) -> None:
    """Teknik ve yönetici rapor sayfalarını üretir.

    Her turda değil: haftalık toplamları çıkaran sorgular veri biriktikçe
    saniyeler sürebiliyor ve haftalık bir özetin dakikalık tazeliğe ihtiyacı yok.
    """
    global _last_reports
    if not config["dashboard"].get("enabled"):
        return
    aralik = config["poll"].get("report_refresh_minutes", 10) * 60
    now = time.time()
    if _last_reports and (now - _last_reports) < aralik:
        return

    klasor = Path(config["dashboard"]["output_file"]).parent
    try:
        for dosya, uretici in (
            (dashboard.TEKNIK_DOSYA, reports_html.teknik),
            (dashboard.YONETICI_DOSYA, reports_html.yonetici),
        ):
            dashboard.write(uretici(store, config, LOGO_DATA_URI), str(klasor / dosya))
    except Exception:
        log.exception("Rapor sayfaları üretilemedi — izleme etkilenmedi.")
        return
    _last_reports = now
    log.debug("Rapor sayfaları güncellendi (%.1f sn)", time.time() - now)


def maybe_send_weekly_report(config: dict[str, Any], store: Store) -> bool:
    """Haftalık raporun zamanı geldiyse gönderir."""
    report_config = config["report"]
    if not report_config.get("weekly_enabled"):
        return False

    now = dt.datetime.now()
    if now.weekday() != WEEKDAYS[report_config["weekly_day"].lower()]:
        return False
    if now.hour != int(report_config["weekly_hour"]):
        return False

    last_run = store.get_job_run("weekly_report")
    if last_run and (time.time() - last_run) < 6 * 86400:
        return False

    return send_weekly_report(config, store)


def send_weekly_report(config: dict[str, Any], store: Store) -> bool:
    """Haftalık raporu üretir, diske yazar ve e-postayla gönderir.

    Diske yazma her koşulda yapılır: e-posta henüz ayarlı değilse bile rapor
    birikir ve dashboard üzerinden okunabilir.
    """
    html_path, md_path = report.save(store, config)
    log.info("Haftalık rapor yazıldı: %s (ve %s)", html_path.name, md_path.name)

    subject, body = report.build(store, config)
    recipients = config["report"]["recipients"] or config["email"]["recipients"]
    sent = notify.send_mail(config, subject, body, recipients)

    # E-posta gönderilemese de iş tamamlanmış sayılır; aksi halde her turda
    # rapor yeniden üretilmeye çalışılırdı.
    store.set_job_run("weekly_report", int(time.time()))
    return sent


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def maybe_send_monthly_report(config: dict[str, Any], store: Store) -> bool:
    """Aylık yönetici raporunun zamanı geldiyse PDF ekiyle gönderir."""
    rc = config["report"]
    if not rc.get("monthly_enabled"):
        return False

    now = dt.datetime.now()
    if now.day != int(rc.get("monthly_day", 1)) or now.hour != int(rc.get("monthly_hour", 9)):
        return False

    # 25 gün: en kısa ay 28 gün olduğu için aynı ay içinde ikinci kez
    # tetiklenmeyi engeller, bir sonraki ayı da kaçırmaz.
    son = store.get_job_run("monthly_report")
    if son and (time.time() - son) < 25 * 86400:
        return False

    return send_monthly_report(config, store)


def send_monthly_report(config: dict[str, Any], store: Store) -> bool:
    """Aylık yönetici raporunu PDF olarak üretip e-postayla gönderir."""
    from . import pdf as pdf_uretici

    rc = config["report"]
    alicilar = rc.get("monthly_recipients") or rc.get("recipients") or config["email"]["recipients"]
    if not alicilar:
        log.warning("Aylık rapor alıcısı tanımlı değil, gönderilmedi.")
        return False

    try:
        icerik = pdf_uretici.uret(store, config, 30)
    except Exception:
        log.exception("Aylık rapor PDF'i üretilemedi.")
        return False

    bugun = dt.date.today()
    # Rapor biten dönemi özetlediği için başlıkta bir önceki ayın adı geçer.
    onceki = (bugun.replace(day=1) - dt.timedelta(days=1))
    donem = f"{AYLAR[onceki.month - 1]} {onceki.year}"
    dosya = f"yurtnet-aylik-rapor-{bugun:%Y-%m-%d}.pdf"

    konu = f"Yurt İnternet — {donem} aylık yönetici raporu"
    gonderildi = notify.send_mail(
        config, konu, _aylik_mail_govdesi(config, store, donem),
        list(alicilar), ekler=[(dosya, icerik, "pdf")],
    )

    # Gönderilemese de iş tamamlanmış sayılır; aksi halde saat boyunca her
    # turda yeniden üretilip denenirdi.
    store.set_job_run("monthly_report", int(time.time()))
    return gonderildi


def _aylik_mail_govdesi(config: dict[str, Any], store: Store, donem: str) -> str:
    """Mail gövdesi kasten kısa: ayrıntı ekteki PDF'te ve panoda."""
    from .render import BASE_FONT, fmt_duration, fmt_pct

    now = int(time.time())
    v = store.weekly_stats(now - 30 * 86400, now)
    hosts = v["hosts"]
    uptime = sum(h["uptime_pct"] for h in hosts) / len(hosts) if hosts else 0.0
    kesinti = sum(
        ariza_suresi(i, now) for i in v["incidents"] if i.code in KESINTI_KODLARI
    )
    adres = notify.pano_adresi(config)
    baglanti = (
        f'<p style="margin:20px 0 0"><a href="{adres}yonetici.html" '
        f'style="color:#2563eb">Panodaki güncel raporu aç</a></p>' if adres else ""
    )
    return (
        f'<div style="{BASE_FONT}max-width:560px;color:#1a1a18;line-height:1.55">'
        f"<h2 style='margin:0 0 4px'>Yurt İnternet — {donem}</h2>"
        f"<p style='margin:0 0 20px;color:#6b6b63'>Aylık yönetici raporu ekte "
        f"PDF olarak.</p>"
        f"<p style='margin:0'><b>{len(hosts)} yurt</b> izlendi · "
        f"başarılı çalışma oranı <b>{fmt_pct(uptime)}</b> · "
        f"toplam kesinti <b>{fmt_duration(kesinti)}</b>.</p>"
        f"{baglanti}"
        f"<p style='margin:24px 0 0;font-size:12px;color:#8a8a80'>"
        f"Bu mesaj yurtnet tarafından otomatik gönderildi.</p></div>"
    )


def loop(config: dict[str, Any], store: Store) -> None:
    interval = config["poll"]["check_interval_minutes"] * 60
    # HTTP sunucusu "planlı kapalı" düğmesini işleyebilsin diye depo ve
    # yeniden çizim geri çağrısı verilir.
    dashboard.serve(config, store=store, yeniden_ciz=lambda: yeniden_ciz(config, store))
    log.info("İzleme başladı — her %d dakikada bir kontrol.", config["poll"]["check_interval_minutes"])

    last_prune = 0.0
    while not _stop:
        cycle_started = time.time()
        try:
            run_cycle(config, store)
            maybe_send_weekly_report(config, store)
            maybe_send_monthly_report(config, store)
        except ZabbixError as exc:
            log.error("Zabbix hatası: %s", exc)
        except Exception:
            log.exception("Beklenmeyen hata — bir sonraki turda tekrar denenecek.")

        if time.time() - last_prune > 86400:
            store.prune(
                config["storage"]["retain_days"],
                config["storage"].get("retain_incident_days"),
            )
            last_prune = time.time()

        # Turun süresini düşerek sabit periyot koru; kapatma sinyaline hızlı tepki ver.
        sleep_for = max(5.0, interval - (time.time() - cycle_started))
        deadline = time.time() + sleep_for
        while not _stop and time.time() < deadline:
            time.sleep(min(1.0, deadline - time.time()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yurtnet", description="Zabbix tabanlı yurt interneti izleme, ön tanı ve raporlama."
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="yapılandırma dosyası")
    parser.add_argument("--once", action="store_true", help="tek tur çalıştır ve çık")
    parser.add_argument("--report-now", action="store_true", help="haftalık raporu hemen gönder")
    parser.add_argument("--monthly-now", action="store_true",
                        help="aylık yönetici raporunu (PDF ekli) hemen gönder")
    parser.add_argument("--test-mail", action="store_true", help="test maili gönder ve çık")
    parser.add_argument("--check", action="store_true", help="ayarları ve Zabbix bağlantısını doğrula")
    parser.add_argument(
        "--dump",
        nargs="?",
        const="envanter.txt",
        metavar="DOSYA",
        help="Zabbix envanterini (hostlar, şablonlar, item key'ler) dosyaya döker",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="ayrıntılı log")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"Yapılandırma hatası: {exc}", file=sys.stderr)
        return 2

    store = Store(config["storage"]["db_file"])

    if args.check:
        return _check(config)
    if args.dump:
        return _dump(config, args.dump)
    if args.test_mail:
        ok = notify.send_mail(
            config,
            "[TEST] Yurt İnternet İzleme",
            "<p style='font-family:sans-serif'>Bu bir test mesajıdır. "
            "SMTP ayarlarınız çalışıyor.</p>",
        )
        return 0 if ok else 1
    if args.report_now:
        send_weekly_report(config, store)
        return 0
    if args.monthly_now:
        return 0 if send_monthly_report(config, store) else 1

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    if args.once:
        try:
            run_cycle(config, store)
        except ZabbixError as exc:
            log.error("Zabbix hatası: %s", exc)
            return 1
        return 0

    loop(config, store)
    return 0


def _dump(config: dict[str, Any], output_file: str) -> int:
    from pathlib import Path

    try:
        with ZabbixClient(config["zabbix"]) as client:
            text = inventory.dump(client, config)
    except ZabbixError as exc:
        print(f"Zabbix bağlantı hatası: {exc}", file=sys.stderr)
        return 1

    path = Path(output_file)
    path.write_text(text, encoding="utf-8")
    print(f"Envanter yazıldı: {path.resolve()}  ({len(text.splitlines())} satır)")
    print("Bu dosya parola/token içermez, olduğu gibi paylaşabilirsiniz.")
    return 0


def _check(config: dict[str, Any]) -> int:
    try:
        with ZabbixClient(config["zabbix"]) as client:
            print(f"Zabbix bağlantısı OK — API sürümü {client.version}")
            hosts = client.get_hosts(config["zabbix"]["host_groups"])
            hosts = collect._apply_exclusions(hosts, config["zabbix"].get("exclude_hosts") or [])
            print(f"İzlenecek host sayısı: {len(hosts)}")
            by_region: dict[str, list[str]] = {}
            for host in hosts:
                _, region = collect.resolve_region(host, config["regions"])
                by_region.setdefault(region, []).append(host.get("name") or host["host"])
            for region in sorted(by_region):
                names = by_region[region]
                print(f"  {region} ({len(names)} yurt)")
                for name in sorted(names):
                    print(f"      · {name}")
            if not hosts:
                print("UYARI: hiç host bulunamadı — zabbix.host_groups ayarını kontrol edin.")
                return 1
    except ZabbixError as exc:
        print(f"Zabbix bağlantı hatası: {exc}", file=sys.stderr)
        return 1
    print("Ayarlar geçerli.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
