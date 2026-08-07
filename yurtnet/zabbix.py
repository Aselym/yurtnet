"""Zabbix JSON-RPC API istemcisi.

Zabbix 5.0 ile 7.x arası sürümlerde çalışır. Kimlik doğrulama biçimi sürüme göre
değiştiği için (6.4'ten itibaren Authorization: Bearer başlığı) önce apiinfo.version
sorulur ve doğru yöntem seçilir.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable

import requests

log = logging.getLogger(__name__)


class ZabbixError(Exception):
    pass


class ZabbixClient:
    def __init__(self, config: dict[str, Any]):
        url = config["url"].rstrip("/")
        if not url.endswith("api_jsonrpc.php"):
            url = f"{url}/api_jsonrpc.php"
        self.url = url
        self.timeout = config.get("timeout", 30)
        self._token_config = config.get("token") or ""
        self._user = config.get("user") or ""
        self._password = config.get("password") or ""

        self._session = requests.Session()
        self._session.verify = config.get("verify_ssl", True)
        self._session.headers.update({"Content-Type": "application/json-rpc"})

        self._request_id = 0
        self._auth: str | None = None
        self._use_bearer = False
        self.version: str = ""

    # ---------------------------------------------------------------- transport

    def _rpc(self, method: str, params: Any, authenticated: bool = True) -> Any:
        self._request_id += 1
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": self._request_id,
        }
        headers: dict[str, str] = {}

        if authenticated and self._auth:
            if self._use_bearer:
                headers["Authorization"] = f"Bearer {self._auth}"
            else:
                payload["auth"] = self._auth

        try:
            response = self._session.post(
                self.url, json=payload, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise ZabbixError(f"Zabbix API'ye ulaşılamadı ({method}): {exc}") from exc
        except ValueError as exc:
            raise ZabbixError(f"Zabbix API geçersiz JSON döndürdü ({method}): {exc}") from exc

        if "error" in data:
            err = data["error"]
            raise ZabbixError(
                f"Zabbix API hatası ({method}): {err.get('message')} {err.get('data', '')}".strip()
            )
        return data["result"]

    # ------------------------------------------------------------------- login

    def login(self) -> None:
        self.version = str(self._rpc("apiinfo.version", {}, authenticated=False))
        major, minor = (list(map(int, self.version.split(".")[:2])) + [0, 0])[:2]
        self._use_bearer = (major, minor) >= (6, 4)

        if self._token_config:
            self._auth = self._token_config
        else:
            # 5.4'ten itibaren parametre adı "user" değil "username".
            key = "username" if (major, minor) >= (5, 4) else "user"
            self._auth = self._rpc(
                "user.login", {key: self._user, "password": self._password}, authenticated=False
            )
        log.info("Zabbix %s bağlantısı kuruldu (bearer=%s)", self.version, self._use_bearer)

    def logout(self) -> None:
        # API token ile giriş yapıldıysa oturum kapatmak gerekmez (ve hata verir).
        if self._auth and not self._token_config:
            try:
                self._rpc("user.logout", [])
            except ZabbixError:
                pass
        self._auth = None

    # -------------------------------------------------------------------- data

    def get_hosts(self, host_groups: Iterable[str]) -> list[dict[str, Any]]:
        """İzlenecek hostları (yurtları) tag ve grup bilgisiyle birlikte getirir."""
        params: dict[str, Any] = {
            "output": ["hostid", "host", "name", "status"],
            "selectTags": ["tag", "value"],
            "selectHostGroups" if self._version_at_least(6, 2) else "selectGroups": ["name"],
            "selectInterfaces": ["ip", "dns", "useip"],
            "filter": {"status": 0},  # sadece izlenen (enabled) hostlar
        }
        groups = [g for g in (host_groups or []) if g]
        if groups:
            group_ids = [g["groupid"] for g in self.get_host_groups(groups)]
            if not group_ids:
                log.warning("Yapılandırmadaki host grupları Zabbix'te bulunamadı: %s", groups)
                return []
            params["groupids"] = group_ids

        hosts = self._rpc("host.get", params)
        for host in hosts:
            # Sürüme göre değişen alan adını tek isme indirgeyelim.
            host["groups"] = host.pop("hostgroups", None) or host.get("groups") or []
            iface = (host.get("interfaces") or [{}])[0]
            host["address"] = (iface.get("ip") if iface.get("useip") == "1" else iface.get("dns")) or ""
        return hosts

    def get_host_groups(self, names: Iterable[str]) -> list[dict[str, Any]]:
        return self._rpc(
            "hostgroup.get", {"output": ["groupid", "name"], "filter": {"name": list(names)}}
        )

    def get_items(self, host_ids: Iterable[str]) -> list[dict[str, Any]]:
        """Hostlara ait, veri toplayan (enabled + supported) tüm item'ları getirir."""
        return self._rpc(
            "item.get",
            {
                "output": ["itemid", "hostid", "key_", "name", "value_type", "units", "status", "state"],
                "hostids": list(host_ids),
                "filter": {"status": 0, "state": 0},
                "webitems": True,
            },
        )

    def get_last_values(
        self, items: list[dict[str, Any]], window_seconds: int
    ) -> dict[str, tuple[float, int]]:
        """itemid -> (son değer, zaman damgası).

        history.get value_type'a göre ayrı tablolardan okuduğu için item'lar
        value_type'a göre gruplanır. Sadece sayısal tipler (0=float, 3=uint) alınır.
        """
        time_from = int(time.time()) - window_seconds
        by_type: dict[int, list[str]] = {}
        for item in items:
            vtype = int(item["value_type"])
            if vtype in (0, 3):
                by_type.setdefault(vtype, []).append(item["itemid"])

        latest: dict[str, tuple[float, int]] = {}
        for vtype, item_ids in by_type.items():
            # Çok sayıda item olduğunda tek istek şişmesin diye parçalayarak sorgula.
            for chunk in _chunks(item_ids, 500):
                rows = self._rpc(
                    "history.get",
                    {
                        "output": ["itemid", "clock", "value"],
                        "history": vtype,
                        "itemids": chunk,
                        "time_from": time_from,
                        "sortfield": "clock",
                        "sortorder": "DESC",
                        "limit": 50000,
                    },
                )
                for row in rows:
                    item_id = row["itemid"]
                    clock = int(row["clock"])
                    known = latest.get(item_id)
                    if known is None or clock > known[1]:
                        try:
                            latest[item_id] = (float(row["value"]), clock)
                        except (TypeError, ValueError):
                            continue
        return latest

    def get_history(
        self, item_ids: list[str], time_from: int, time_till: int, value_type: int = 3
    ) -> dict[str, list[tuple[int, float]]]:
        """itemid -> [(zaman, değer), ...], eskiden yeniye sıralı.

        Trafik grafiği için. `get_last_values` yalnız son değeri verir; burada
        aralığın tamamı gerekiyor. value_type tabloyu belirler (0=float, 3=uint)
        ve yanlış verilirse Zabbix boş liste döner, hata vermez.
        """
        seri: dict[str, list[tuple[int, float]]] = {i: [] for i in item_ids}
        for chunk in _chunks(list(item_ids), 20):
            rows = self._rpc(
                "history.get",
                {
                    "output": ["itemid", "clock", "value"],
                    "history": value_type,
                    "itemids": chunk,
                    "time_from": time_from,
                    "time_till": time_till,
                    "sortfield": "clock",
                    "sortorder": "ASC",
                    "limit": 200000,
                },
            )
            for row in rows:
                try:
                    seri[row["itemid"]].append((int(row["clock"]), float(row["value"])))
                except (KeyError, TypeError, ValueError):
                    continue
        return seri

    def get_problems(self, host_ids: Iterable[str]) -> list[dict[str, Any]]:
        """Açık (çözülmemiş) Zabbix problemlerini getirir — ön tanı için ek sinyal."""
        return self._rpc(
            "problem.get",
            {
                "output": "extend",
                "hostids": list(host_ids),
                "recent": False,
                "sortfield": ["eventid"],
                "sortorder": "DESC",
            },
        )

    def map_events_to_hosts(self, problems: list[dict[str, Any]]) -> dict[str, list[dict]]:
        """problem.get hostid döndürmez; trigger üzerinden host eşlemesi yapılır."""
        object_ids = sorted({p["objectid"] for p in problems})
        if not object_ids:
            return {}
        triggers = self._rpc(
            "trigger.get",
            {"output": ["triggerid"], "triggerids": object_ids, "selectHosts": ["hostid"]},
        )
        trigger_hosts = {
            t["triggerid"]: [h["hostid"] for h in t.get("hosts", [])] for t in triggers
        }
        by_host: dict[str, list[dict]] = {}
        for problem in problems:
            for host_id in trigger_hosts.get(problem["objectid"], []):
                by_host.setdefault(host_id, []).append(problem)
        return by_host

    # ----------------------------------------------------------------- helpers

    def _version_at_least(self, major: int, minor: int) -> bool:
        if not self.version:
            return False
        parts = (list(map(int, self.version.split(".")[:2])) + [0, 0])[:2]
        return (parts[0], parts[1]) >= (major, minor)

    def __enter__(self) -> "ZabbixClient":
        self.login()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.logout()


def _chunks(seq: list[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]
