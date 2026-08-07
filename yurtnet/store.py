"""SQLite tabanlı ölçüm ve arıza kaydı.

İki şey için gerekli:
  1. Flapping / trend tespiti (geçmişe bakmadan anlaşılmaz),
  2. Haftalık rapor (kesinti süreleri, en sorunlu yurtlar).
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from .collect import HostSnapshot
from .diagnose import Finding

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
    ts        INTEGER NOT NULL,
    hostid    TEXT    NOT NULL,
    host      TEXT    NOT NULL,
    name      TEXT    NOT NULL,
    region    TEXT    NOT NULL,
    reachable INTEGER,          -- 1 up, 0 down, NULL bilinmiyor
    has_data  INTEGER NOT NULL,
    loss_pct  REAL,
    latency_ms REAL,
    cpu_pct   REAL,
    mem_pct   REAL,
    in_bps    REAL,
    out_bps   REAL,
    util_pct  REAL
);
CREATE INDEX IF NOT EXISTS idx_meas_host_ts ON measurements (hostid, ts);
CREATE INDEX IF NOT EXISTS idx_meas_ts ON measurements (ts);

CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key   TEXT    NOT NULL,
    scope       TEXT    NOT NULL,
    hostid      TEXT,
    host        TEXT,
    name        TEXT,
    region      TEXT,
    code        TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    title       TEXT    NOT NULL,
    detail      TEXT,
    action      TEXT,
    remote_fixable INTEGER,
    started_at  INTEGER NOT NULL,
    last_seen   INTEGER NOT NULL,
    ended_at    INTEGER,
    notified_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_inc_open ON incidents (ended_at, dedup_key);
CREATE INDEX IF NOT EXISTS idx_inc_started ON incidents (started_at);

CREATE TABLE IF NOT EXISTS job_runs (
    job      TEXT PRIMARY KEY,
    last_run INTEGER NOT NULL
);

-- Bilinçli olarak kapatılmış yurtlar (ör. yaz döneminde boş yurdun interneti).
-- Arıza sayılmaz, raporlarda erişilebilirlik hesabına katılmaz.
CREATE TABLE IF NOT EXISTS planned_down (
    hostid   TEXT PRIMARY KEY,
    host     TEXT,
    name     TEXT,
    note     TEXT,
    since    INTEGER NOT NULL
);
"""


@dataclass
class Incident:
    id: int
    dedup_key: str
    scope: str
    hostid: str | None
    host: str | None
    name: str | None
    region: str | None
    code: str
    severity: str
    title: str
    detail: str
    action: str
    remote_fixable: bool
    started_at: int
    last_seen: int
    ended_at: int | None
    notified_at: int | None

    @property
    def duration_seconds(self) -> int:
        return ariza_suresi(self, int(time.time()))


# "İnternet kullanılamıyordu" anlamına gelen kodlar. Tek bir yerde tanımlı
# olmaları şart: teknik rapor, yönetici raporu ve PDF farklı listeler
# kullandığında aynı başlık ("Toplam kesinti") altında farklı sayılar çıkıyordu.
KESINTI_KODLARI = ("HOST_DOWN", "NO_DATA", "WAN_SILENT", "WAN_IFACE_DOWN")

# İzleme durduğunda (servis kapalı, makine kapalı, ağ koptu) açık bir arıza
# kaydı "hâlâ sürüyor" görünür ve o boşluğun tamamı kesintiye yazılır. Oysa o
# süre boyunca ölçüm yapılmadı: sorunun devam ettiği bilinmiyor, iddia edilemez.
# Bu yüzden süre, sorunun en son GÖRÜLDÜĞÜ ana kadar sayılır.
IZLEME_BOSLUK_TOLERANSI = 600  # 10 dk


# Yukarıdaki ariza_suresi()'nin SQL karşılığı. Toplamlar veritabanında
# hesaplandığı için aynı kural iki dilde yazılmak zorunda; ikisi ayrışırsa
# aynı başlık altında farklı rakamlar çıkar (bir kez çıktı da).
#   ? yerine "şimdi" damgası bağlanır.
SQL_ARIZA_SURESI = (
    f"MAX(0, MIN(COALESCE(ended_at, ?), last_seen + {IZLEME_BOSLUK_TOLERANSI}) - started_at)"
)


def ariza_suresi(i: "Incident", now: int, tolerans: int = IZLEME_BOSLUK_TOLERANSI) -> int:
    """Bir arızanın ölçümle desteklenen süresi.

    Normal işleyişte last_seen her turda tazelenir, dolayısıyla üst sınır
    devreye girmez ve sonuç bitiş - başlangıçtır. Yalnızca izleme boşluğu
    varsa süre kırpılır.
    """
    bitis = i.ended_at if i.ended_at is not None else now
    return max(0, min(bitis, i.last_seen + tolerans) - i.started_at)


class Store:
    def __init__(self, db_file: str):
        self.db_file = db_file
        with self._conn() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Mevcut veritabanlarına sonradan eklenen sütunlar."""
        sutunlar = {r["name"] for r in conn.execute("PRAGMA table_info(measurements)")}
        if "planned" not in sutunlar:
            # Ölçüm anındaki "bilinçli kapalı" durumu satıra yazılır; geçmiş
            # erişilebilirlik hesabı sonradan değişen bir bayrağa bağlı kalmasın.
            conn.execute(
                "ALTER TABLE measurements ADD COLUMN planned INTEGER NOT NULL DEFAULT 0"
            )
        if "if_errors" not in sutunlar:
            # Arayüz hata sayacı kümülatiftir: cihaz açıldığından beri biriken
            # toplamı verir. Anlamlı olan mutlak değer değil, iki ölçüm
            # arasındaki artıştır — bu yüzden geçmiş değer saklanır.
            conn.execute("ALTER TABLE measurements ADD COLUMN if_errors REAL")

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_file, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -------------------------------------------------------------- ölçümler

    def record(self, snapshots: list[HostSnapshot], planned: set[str] | None = None) -> None:
        planned = planned or set()
        rows = [
            (
                s.ts, s.hostid, s.host, s.name, s.region,
                None if s.reachable is None else int(s.reachable),
                int(s.has_data), s.loss_pct, s.latency_ms, s.cpu_pct, s.mem_pct,
                s.in_bps, s.out_bps, s.util_pct, int(s.hostid in planned), s.if_errors,
            )
            for s in snapshots
        ]
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO measurements (ts, hostid, host, name, region, reachable, has_data,"
                " loss_pct, latency_ms, cpu_pct, mem_pct, in_bps, out_bps, util_pct, planned,"
                " if_errors) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )

    def onceki_if_errors(self) -> dict[str, float]:
        """Her yurdun en son kaydedilen arayüz hata sayacı.

        Kümülatif sayaçta "sıfırdan büyük" olmak bir şey ifade etmez; üç ay
        önce olmuş bir hata da sayaçta durur. Anlamlı olan artıştır.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT hostid, if_errors FROM measurements m WHERE if_errors IS NOT NULL"
                " AND ts = (SELECT MAX(ts) FROM measurements x WHERE x.hostid = m.hostid"
                "           AND x.if_errors IS NOT NULL)"
            ).fetchall()
        return {r["hostid"]: r["if_errors"] for r in rows}

    def izleme_bosluklari(self, since: int, until: int, esik: int = 600) -> list[tuple[int, int]]:
        """İzlemenin durduğu aralıklar: (başlangıç, bitiş) listesi.

        Servis kapalıyken hiçbir ölçüm yazılmaz. Rapor bunu söylemezse "o gün
        her şey yolundaydı" gibi okunur; oysa bakılmamıştır. Ardışık ölçüm
        zamanları arasındaki eşikten büyük boşluklar bulunur.
        """
        with self._conn() as conn:
            zamanlar = [
                r["ts"] for r in conn.execute(
                    "SELECT DISTINCT ts FROM measurements WHERE ts BETWEEN ? AND ? ORDER BY ts",
                    (since, until),
                )
            ]
        return [(a, b) for a, b in zip(zamanlar, zamanlar[1:]) if b - a > esik]

    def olcum_baglami(self, hostid: str, ts: int, pencere: int = 900) -> dict[str, Any] | None:
        """Arıza anına en yakın ölçüm satırı.

        Teknik servis raporunda "bu kayıt açıldığında hattın hâli neydi"
        sorusunun cevabı: gecikme, kayıp, trafik, doluluk. Arıza kaydında bu
        değerler saklanmıyor; ölçüm tablosundan geriye dönük okunuyor.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM measurements WHERE hostid = ? AND ts BETWEEN ? AND ?"
                " ORDER BY ABS(ts - ?) LIMIT 1",
                (hostid, ts - pencere, ts + pencere, ts),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------- bilinçli kapatma

    def planned_down(self) -> dict[str, dict[str, Any]]:
        """Şu an planlı kapalı işaretli yurtlar: hostid -> kayıt."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM planned_down").fetchall()
        return {r["hostid"]: dict(r) for r in rows}

    def set_planned(self, hostid: str, host: str, name: str, note: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO planned_down (hostid, host, name, note, since)"
                " VALUES (?,?,?,?,?)"
                " ON CONFLICT(hostid) DO UPDATE SET note = excluded.note",
                (hostid, host, name, note, int(time.time())),
            )

    def clear_planned(self, hostid: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM planned_down WHERE hostid = ?", (hostid,))

    def backfill_current_outage(self, hostid: str) -> tuple[int, int]:
        """Süregelen kesintiyi geçmişe dönük "planlı" olarak işaretler.

        Kullanıcı bir yurdu bilinçli kapalı işaretlediğinde kastettiği şey
        "şu an devam eden bu kapalılık kasıtlı" demektir. Yalnızca ileriye
        dönük uygulanırsa rapor haftalarca yanlış kalır. Bu yüzden yurdun
        en son ayakta görüldüğü ana kadar geri gidilir — daha eskisine
        dokunulmaz, ilgisiz geçmiş kesintiler korunur.

        Dönen: (düzeltilen ölçüm sayısı, silinen arıza kaydı sayısı)
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(ts) AS son FROM measurements"
                " WHERE hostid = ? AND reachable = 1 AND has_data = 1",
                (hostid,),
            ).fetchone()
            baslangic = (row["son"] or 0) if row else 0

            olcum = conn.execute(
                "UPDATE measurements SET planned = 1"
                " WHERE hostid = ? AND ts > ? AND (reachable = 0 OR has_data = 0)",
                (hostid, baslangic),
            ).rowcount

            # Bu kesinti penceresinde açılmış arıza kayıtları gerçek arıza
            # değildi. Kapanmış olanlar da silinir: aynı kesinti, uygulama her
            # yeniden başladığında yeni bir kayıt doğurabiliyor ve hepsi
            # raporda ayrı ayrı görünür.
            ariza = conn.execute(
                "DELETE FROM incidents WHERE hostid = ? AND started_at > ?"
                " AND code IN ('HOST_DOWN','NO_DATA','WAN_SILENT','WAN_IFACE_DOWN','FLAPPING')",
                (hostid, baslangic),
            ).rowcount
        return olcum, ariza

    def transitions_last_hour(self, hostid: str) -> int:
        """Son 1 saatte up<->down kaç kez değişmiş."""
        since = int(time.time()) - 3600
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT reachable FROM measurements"
                " WHERE hostid = ? AND ts >= ? AND reachable IS NOT NULL ORDER BY ts",
                (hostid, since),
            ).fetchall()
        states = [r["reachable"] for r in rows]
        return sum(1 for a, b in zip(states, states[1:]) if a != b)

    # --------------------------------------------------------------- arızalar

    def sync_incidents(
        self, findings: list[Finding], now: int | None = None
    ) -> tuple[list[Incident], list[Incident]]:
        """Aktif bulguları veritabanıyla eşitler.

        Dönen: (bildirime aday açık arızalar, bu turda kapanan arızalar)
        "Bildirime aday" = yeni açılmış ya da soğuma süresi dolmuş arızalar;
        cooldown kararı çağıran tarafta verilir.
        """
        now = now or int(time.time())
        active_keys = {f.dedup_key for f in findings}
        opened_or_updated: list[Incident] = []

        with self._conn() as conn:
            open_rows = conn.execute(
                "SELECT * FROM incidents WHERE ended_at IS NULL"
            ).fetchall()
            open_by_key = {r["dedup_key"]: r for r in open_rows}

            for finding in findings:
                existing = open_by_key.get(finding.dedup_key)
                if existing:
                    conn.execute(
                        "UPDATE incidents SET last_seen = ?, severity = ?, title = ?,"
                        " detail = ?, action = ? WHERE id = ?",
                        (now, finding.severity, finding.title, finding.detail,
                         finding.action, existing["id"]),
                    )
                    row = conn.execute(
                        "SELECT * FROM incidents WHERE id = ?", (existing["id"],)
                    ).fetchone()
                else:
                    cursor = conn.execute(
                        "INSERT INTO incidents (dedup_key, scope, hostid, host, name, region,"
                        " code, severity, title, detail, action, remote_fixable, started_at,"
                        " last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            finding.dedup_key, finding.scope, finding.hostid, finding.host,
                            finding.name, finding.region, finding.code, finding.severity,
                            finding.title, finding.detail, finding.action,
                            int(finding.remote_fixable), now, now,
                        ),
                    )
                    row = conn.execute(
                        "SELECT * FROM incidents WHERE id = ?", (cursor.lastrowid,)
                    ).fetchone()
                opened_or_updated.append(_to_incident(row))

            kapanacak = [r for key, r in open_by_key.items() if key not in active_keys]
            resolved: list[Incident] = []
            for satir in kapanacak:
                incident_id = satir["id"]
                # Bitiş zamanı "şimdi" değil, sorunun en son görüldüğü andan
                # en fazla tolerans kadar sonrası. İzleme gece boyunca durmuşsa
                # sabah açılışta 15 saatlik kesinti uydurulmasın.
                bitis = min(now, satir["last_seen"] + IZLEME_BOSLUK_TOLERANSI)
                conn.execute(
                    "UPDATE incidents SET ended_at = ? WHERE id = ?", (bitis, incident_id)
                )
                row = conn.execute(
                    "SELECT * FROM incidents WHERE id = ?", (incident_id,)
                ).fetchone()
                resolved.append(_to_incident(row))

        return opened_or_updated, resolved

    def acik_incident_severity(self) -> dict[str, str]:
        """Açık arızası olan yurtların en ağır seviyesi: hostid -> severity."""
        sira = {"info": 0, "warning": 1, "critical": 2}
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT hostid, severity FROM incidents"
                " WHERE ended_at IS NULL AND hostid IS NOT NULL"
            ).fetchall()
        sonuc: dict[str, str] = {}
        for r in rows:
            mevcut = sonuc.get(r["hostid"])
            if mevcut is None or sira.get(r["severity"], 0) > sira.get(mevcut, 0):
                sonuc[r["hostid"]] = r["severity"]
        return sonuc

    def acik_dedup_keys(self) -> set[str]:
        """Halen açık olan arızaların kimlikleri.

        Zaten açık bir arızanın bulgusu yeniden "teyit" edilmek zorunda değildir;
        aksi halde uygulama her yeniden başladığında açık kayıtlar kapanıp
        yeniden açılır ve arıza sayısı sahte biçimde şişer.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT dedup_key FROM incidents WHERE ended_at IS NULL"
            ).fetchall()
        return {r["dedup_key"] for r in rows}

    def acik_incidentlar(self) -> list[Incident]:
        """Halen açık arıza kayıtlarının tamamı.

        Ekran modunda "bu yurt ne zamandır kopuk" sorusunun cevabı buradan
        gelir; anlık bulgu sorunun ne zaman başladığını bilmez.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE ended_at IS NULL ORDER BY started_at"
            ).fetchall()
        return [_to_incident(r) for r in rows]

    def mark_notified(self, incident_ids: list[int], now: int | None = None) -> None:
        if not incident_ids:
            return
        now = now or int(time.time())
        with self._conn() as conn:
            conn.executemany(
                "UPDATE incidents SET notified_at = ? WHERE id = ?",
                [(now, i) for i in incident_ids],
            )

    # --------------------------------------------------- kapasite öğrenme

    # ISP hat hızları için tipik abonelik basamakları.
    CAPACITY_TIERS = (10, 16, 20, 25, 35, 50, 75, 100, 150, 200, 250, 300, 500, 1000)

    def learned_capacities(
        self, min_days: int = 7, min_samples: int = 500
    ) -> dict[str, float]:
        """Geçmiş trafikten yurt başına tahmini hat kapasitesi (Mbps).

        Gerçek abonelik hızı bilinmediğinde kullanılır: yeterli veri biriktikten
        sonra gözlenen tepe trafiğe göre en yakın standart abonelik basamağına
        yuvarlanır. Az veriyle yanlış tahmin yapmamak için eşikler konmuştur.
        """
        since = int(time.time()) - min_days * 86400
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT hostid, COUNT(*) AS n,"
                "       MAX(COALESCE(in_bps, 0)) AS peak_in,"
                "       MAX(COALESCE(out_bps, 0)) AS peak_out"
                " FROM measurements WHERE ts >= ? GROUP BY hostid",
                (since,),
            ).fetchall()

        estimates: dict[str, float] = {}
        for row in rows:
            if (row["n"] or 0) < min_samples:
                continue
            peak_mbps = max(row["peak_in"] or 0, row["peak_out"] or 0) / 1_000_000
            if peak_mbps < 1:  # anlamlı trafik görülmemiş
                continue
            # Tepe değerin hemen üstündeki standart basamak abonelik hızı sayılır.
            tier = next(
                (t for t in self.CAPACITY_TIERS if t >= peak_mbps * 1.02), None
            )
            estimates[row["hostid"]] = float(tier) if tier else round(peak_mbps)
        return estimates

    # ------------------------------------------------------------ raporlama

    def weekly_stats(self, since: int, until: int) -> dict[str, Any]:
        """Haftalık rapor için özet istatistikler."""
        with self._conn() as conn:
            total_checks = conn.execute(
                "SELECT COUNT(*) c FROM measurements WHERE ts BETWEEN ? AND ?", (since, until)
            ).fetchone()["c"]

            # planned = 1 olan ölçümler erişilebilirlik hesabına katılmaz:
            # bilinçli kapatılmış bir yurdun kapalı olması arıza değildir.
            per_host = conn.execute(
                "SELECT hostid, name, region,"
                "       SUM(CASE WHEN planned = 0 THEN 1 ELSE 0 END) AS checks,"
                "       SUM(CASE WHEN planned = 0 AND (reachable = 0 OR has_data = 0)"
                "            THEN 1 ELSE 0 END) AS down,"
                "       SUM(planned) AS planned_checks,"
                # Gözlem süresi ölçüm sayısından türetilemez: kontrol aralığı
                # zaman içinde değişebiliyor. Gerçek zaman aralığı kullanılır.
                "       MIN(ts) AS ilk_ts, MAX(ts) AS son_ts,"
                "       AVG(CASE WHEN planned = 0 THEN latency_ms END) AS avg_latency,"
                "       AVG(CASE WHEN planned = 0 THEN loss_pct END) AS avg_loss,"
                "       MAX(util_pct) AS peak_util,"
                "       AVG(util_pct) AS avg_util"
                " FROM measurements WHERE ts BETWEEN ? AND ?"
                " GROUP BY hostid ORDER BY down DESC, avg_loss DESC",
                (since, until),
            ).fetchall()

            incidents = conn.execute(
                "SELECT * FROM incidents WHERE started_at BETWEEN ? AND ? ORDER BY started_at",
                (since, until),
            ).fetchall()

            by_code = conn.execute(
                "SELECT code, COUNT(*) AS n,"
                f"       SUM({SQL_ARIZA_SURESI}) AS total_seconds"
                " FROM incidents WHERE started_at BETWEEN ? AND ?"
                " GROUP BY code ORDER BY n DESC",
                (until, since, until),
            ).fetchall()

            by_region = conn.execute(
                "SELECT region, COUNT(*) AS n FROM incidents"
                " WHERE started_at BETWEEN ? AND ? GROUP BY region ORDER BY n DESC",
                (since, until),
            ).fetchall()

        hosts = []
        for row in per_host:
            checks = row["checks"] or 0
            down = row["down"] or 0
            hosts.append(
                {
                    "hostid": row["hostid"],
                    "name": row["name"],
                    "region": row["region"],
                    "checks": checks,
                    "down": down,
                    "planned_checks": row["planned_checks"] or 0,
                    "gozlem_sn": max(0, (row["son_ts"] or 0) - (row["ilk_ts"] or 0)),
                    # Tamamı planlı kapalıysa erişilebilirlik "0" değil "ölçülmedi";
                    # 100 kabul edilerek ortalamayı aşağı çekmesi engellenir.
                    "uptime_pct": (100.0 * (checks - down) / checks) if checks else 100.0,
                    "avg_latency": row["avg_latency"],
                    "avg_loss": row["avg_loss"],
                    "peak_util": row["peak_util"],
                    "avg_util": row["avg_util"],
                }
            )

        return {
            "since": since,
            "until": until,
            "total_checks": total_checks,
            "hosts": hosts,
            "incidents": [_to_incident(r) for r in incidents],
            "by_code": [dict(r) for r in by_code],
            "by_region": [dict(r) for r in by_region],
        }

    def daily_summary(self, since: int, until: int) -> list[dict[str, Any]]:
        """Gün gün erişilebilirlik, gecikme ve kesinti süresi.

        Yönetici raporundaki eğilim grafikleri bunu kullanır: tek bir haftalık
        ortalama, sorunun hangi gün yoğunlaştığını gizler.
        """
        with self._conn() as conn:
            olcum = conn.execute(
                "SELECT date(ts, 'unixepoch', 'localtime') AS gun,"
                "       COUNT(*) AS kontrol,"
                "       SUM(CASE WHEN reachable = 0 OR has_data = 0 THEN 1 ELSE 0 END) AS basarisiz,"
                "       AVG(latency_ms) AS ort_gecikme,"
                "       AVG(loss_pct) AS ort_kayip"
                " FROM measurements WHERE ts BETWEEN ? AND ?"
                " GROUP BY gun ORDER BY gun",
                (since, until),
            ).fetchall()

            # Kesinti süresi yalnızca gerçek erişim kaybından sayılır. İzleme
            # eksikliği (NO_IF_DATA) veya yavaşlık uyarısı da toplansaydı,
            # "bu gün 100 saat kesinti oldu" gibi yanıltıcı rakamlar çıkardı.
            kesinti_kodlari = KESINTI_KODLARI
            yer = ",".join("?" * len(kesinti_kodlari))
            ariza = conn.execute(
                "SELECT date(started_at, 'unixepoch', 'localtime') AS gun,"
                "       COUNT(*) AS adet,"
                f"       SUM(CASE WHEN code IN ({yer})"
                f"            THEN {SQL_ARIZA_SURESI} ELSE 0 END) AS kesinti_sure"
                " FROM incidents WHERE started_at BETWEEN ? AND ?"
                " GROUP BY gun",
                (*kesinti_kodlari, until, since, until),
            ).fetchall()

        ariza_map = {r["gun"]: r for r in ariza}
        gunler = []
        for row in olcum:
            kontrol = row["kontrol"] or 0
            basarisiz = row["basarisiz"] or 0
            a = ariza_map.get(row["gun"])
            gunler.append(
                {
                    "gun": row["gun"],
                    "kontrol": kontrol,
                    "basarisiz": basarisiz,
                    "uptime_pct": (100.0 * (kontrol - basarisiz) / kontrol) if kontrol else 0.0,
                    "ort_gecikme": row["ort_gecikme"],
                    "ort_kayip": row["ort_kayip"],
                    "ariza_adet": (a["adet"] if a else 0),
                    "kesinti_sure": (a["kesinti_sure"] if a else 0) or 0,
                }
            )
        return gunler

    # ------------------------------------------------------------------ bakım

    def haftalik_seri(self, hafta: int = 8, now: int | None = None) -> list[dict[str, Any]]:
        """Son N haftanın özeti, eskiden yeniye.

        Tek bir haftanın rakamı ("60 olay") tek başına anlamsızdır; okuyanın
        karşılaştıracak bir şeyi olmalı. Bu seri hem geçen haftayla kıyas hem
        de eğilim grafiği için kullanılır.

        Verisi olmayan haftalar `veri_var: False` ile döner — sıfır ile
        "ölçülmedi" birbirine karışmasın.
        """
        now = now or int(time.time())
        basla = now - hafta * 604800

        with self._conn() as conn:
            olcum = conn.execute(
                "SELECT CAST((? - ts) / 604800 AS INTEGER) AS kova,"
                "       SUM(CASE WHEN planned = 0 THEN 1 ELSE 0 END) AS kontrol,"
                "       SUM(CASE WHEN planned = 0 AND (reachable = 0 OR has_data = 0)"
                "            THEN 1 ELSE 0 END) AS basarisiz"
                " FROM measurements WHERE ts BETWEEN ? AND ? GROUP BY kova",
                (now, basla, now),
            ).fetchall()

            kesinti_kodlari = KESINTI_KODLARI
            izleme_kodlari = ("NO_IF_DATA", "STALE_DATA")
            yer_k = ",".join("?" * len(kesinti_kodlari))
            yer_i = ",".join("?" * len(izleme_kodlari))
            ariza = conn.execute(
                "SELECT CAST((? - started_at) / 604800 AS INTEGER) AS kova,"
                f"       SUM(CASE WHEN code NOT IN ({yer_i}) THEN 1 ELSE 0 END) AS olay,"
                f"       SUM(CASE WHEN code IN ({yer_k})"
                f"            THEN {SQL_ARIZA_SURESI} ELSE 0 END) AS kesinti,"
                "       COUNT(DISTINCT hostid) AS yurt"
                " FROM incidents WHERE started_at BETWEEN ? AND ? GROUP BY kova",
                (now, *izleme_kodlari, *kesinti_kodlari, now, basla, now),
            ).fetchall()

        o = {r["kova"]: r for r in olcum}
        a = {r["kova"]: r for r in ariza}
        seri = []
        for kova in range(hafta - 1, -1, -1):  # eskiden yeniye
            om, am = o.get(kova), a.get(kova)
            kontrol = (om["kontrol"] if om else 0) or 0
            basarisiz = (om["basarisiz"] if om else 0) or 0
            seri.append(
                {
                    "kova": kova,
                    "bitis": now - kova * 604800,
                    "veri_var": kontrol > 0,
                    "kontrol": kontrol,
                    "uptime_pct": (100.0 * (kontrol - basarisiz) / kontrol) if kontrol else None,
                    "olay": (am["olay"] if am else 0) or 0,
                    "kesinti_sn": (am["kesinti"] if am else 0) or 0,
                    "etkilenen_yurt": (am["yurt"] if am else 0) or 0,
                }
            )
        return seri

    def veri_baslangici(self) -> int | None:
        """En eski ölçümün zamanı. Raporun kaç günlük veriye dayandığını söylemek için."""
        with self._conn() as conn:
            row = conn.execute("SELECT MIN(ts) AS ilk FROM measurements").fetchone()
        return row["ilk"] if row and row["ilk"] else None

    def get_job_run(self, job: str) -> int | None:
        with self._conn() as conn:
            row = conn.execute("SELECT last_run FROM job_runs WHERE job = ?", (job,)).fetchone()
        return row["last_run"] if row else None

    def set_job_run(self, job: str, ts: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO job_runs (job, last_run) VALUES (?, ?)"
                " ON CONFLICT(job) DO UPDATE SET last_run = excluded.last_run",
                (job, ts),
            )

    def prune(self, retain_days: int, retain_incident_days: int | None = None) -> None:
        """Eski kayıtları siler.

        Ham ölçümler ile arıza kayıtları ayrı sürelerle tutulur: ölçümler hacimli
        ve kısa vadede işe yarar (haftalık rapor 7 gün, kapasite öğrenme 7 gün),
        arıza kayıtları ise küçük ama uzun vadeli trend için değerlidir.
        """
        now = int(time.time())
        with self._conn() as conn:
            silinen = conn.execute(
                "DELETE FROM measurements WHERE ts < ?", (now - retain_days * 86400,)
            ).rowcount
            conn.execute(
                "DELETE FROM incidents WHERE ended_at IS NOT NULL AND ended_at < ?",
                (now - (retain_incident_days or retain_days) * 86400,),
            )

        # VACUUM işlem içinde çalışmaz; silme sonrası ayrı bağlantıda yapılır.
        if silinen:
            conn = sqlite3.connect(self.db_file, timeout=60, isolation_level=None)
            try:
                conn.execute("VACUUM")  # boşalan alanı diske geri ver
            finally:
                conn.close()


def _to_incident(row: sqlite3.Row) -> Incident:
    return Incident(
        id=row["id"],
        dedup_key=row["dedup_key"],
        scope=row["scope"],
        hostid=row["hostid"],
        host=row["host"],
        name=row["name"],
        region=row["region"],
        code=row["code"],
        severity=row["severity"],
        title=row["title"],
        detail=row["detail"] or "",
        action=row["action"] or "",
        remote_fixable=bool(row["remote_fixable"]),
        started_at=row["started_at"],
        last_seen=row["last_seen"],
        ended_at=row["ended_at"],
        notified_at=row["notified_at"],
    )
