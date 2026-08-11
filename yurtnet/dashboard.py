"""Tüm yurtların tek ekranda görüldüğü HTML tablosunu üretir ve yayınlar.

Tablo her kontrol turunda diske yazılır; tarayıcı da meta refresh ile
dashboard.refresh_minutes aralığında kendini yeniler.
"""

from __future__ import annotations

import hashlib
import hmac
import http.server
import logging
import secrets
import socketserver
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any

from . import auth, pages
from .brand import LOGO_DATA_URI
from .collect import HostSnapshot
from .diagnose import Finding
from .render import SEVERITY_COLOR, esc, fmt_bps, fmt_duration, fmt_ms, fmt_pct, fmt_time

log = logging.getLogger(__name__)

TEKNIK_DOSYA = "teknik.html"
EKRAN_DOSYA = "ekran.html"
YONETICI_DOSYA = "yonetici.html"

# hostid -> (görünen ad, teknik ad). Son çizimde doldurulur; "planlı kapalı"
# kaydına yurt adını yazabilmek için gerekir.
_HOST_ADLARI: dict[str, tuple[str, str]] = {}


def _host_adi(hostid: str) -> tuple[str, str]:
    return _HOST_ADLARI.get(hostid, ("", ""))

CSS = """
.tools{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
input,select{background:var(--surface);color:var(--ink);border:1px solid var(--line);
             border-radius:7px;padding:8px 11px;font-size:13px;font-family:inherit}
input{min-width:220px;flex:1}
.wrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px}
.wrap table{min-width:1040px}
/* top:0 olmalı. .wrap'te overflow-x:auto olduğu için dikey taşma da "auto"ya
   dönüyor ve kutu yapışkan konumlandırmanın referansı oluyor; sıfırdan büyük
   bir top değeri başlığı kutunun içinde aşağı itip ilk satırın üstüne bindirir. */
.wrap th{position:sticky;top:0;background:var(--surface);cursor:pointer;user-select:none;z-index:2}
.wrap td{vertical-align:top}
.badge{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;font-weight:600;white-space:nowrap}
.name{font-weight:600}
/* Ön tanı, tablodaki en önemli metin: okunması gereken tek yer burası,
   diğer hücreler rakam. Bu yüzden gövde yazısından bir tık büyük. */
.diag{font-size:13.5px;line-height:1.55;max-width:460px}
.diag .act{color:var(--muted);display:block;margin-top:5px;font-size:13px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.warn{color:var(--uyari-ink);font-weight:600}
.crit{color:var(--kritik-ink);font-weight:600}
.dim{color:var(--muted)}
.banner{background:rgba(208,59,59,.10);border:1px solid rgba(208,59,59,.35);
        color:var(--kritik-ink);border-radius:9px;padding:11px 14px;margin-bottom:12px;font-size:13.5px}
.hidden{display:none}
/* bilinçli kapatma düğmesi */
.pl{display:flex;gap:5px;align-items:center;margin-top:7px;flex-wrap:wrap}
.pl input[type=text]{min-width:0;width:135px;padding:4px 8px;font-size:11.5px;border-radius:5px}
.pl button{font-family:inherit;font-size:11.5px;padding:4px 10px;border-radius:5px;
           border:1px solid var(--line);background:var(--surface);color:var(--ink2);cursor:pointer}
.pl button:hover{color:var(--ink);border-color:var(--axis)}
.pl button.geri{border-color:rgba(12,163,12,.4);color:var(--iyi-ink)}
"""

JS = """
const q=document.getElementById('q'),rg=document.getElementById('rg'),st=document.getElementById('st');
// Sayfa dakikada bir kendini yeniliyor. Arama metni, filtreler ve kaydirma konumu
// saklanmazsa kullanici her yenilemede yazdigini kaybeder; tablo kullanilamaz hale gelir.
const KEY='yurtnet.filtre';
function kaydet(){
  try{sessionStorage.setItem(KEY,JSON.stringify(
    {q:q.value,rg:rg.value,st:st.value,y:window.scrollY}));}catch(e){}
}
function filtreleriGeriYukle(){
  try{
    const s=JSON.parse(sessionStorage.getItem(KEY)||'{}');
    if(s.q)q.value=s.q; if(s.rg)rg.value=s.rg; if(s.st)st.value=s.st;
    return s.y||0;
  }catch(e){ return 0; }
}
function apply(){
  const t=q.value.toLowerCase(), r=rg.value, s=st.value;
  let shown=0;
  document.querySelectorAll('tbody tr').forEach(tr=>{
    const ok=(!t||tr.dataset.search.includes(t))&&(!r||tr.dataset.region===r)&&(!s||tr.dataset.sev===s);
    tr.classList.toggle('hidden',!ok); if(ok)shown++;
  });
  document.getElementById('count').textContent=shown;
}
[q,rg,st].forEach(el=>el.addEventListener('input',()=>{apply();kaydet();}));
window.addEventListener('scroll',()=>{clearTimeout(window._kt);window._kt=setTimeout(kaydet,250);});
// Once filtreler geri yuklenip uygulanir, sonra kaydirma konumu: satirlar
// gizlenince sayfa yuksekligi degistigi icin sira onemli.
const _y = filtreleriGeriYukle();
apply();
if(_y) window.scrollTo(0,_y);
// Kullanici arama kutusuna yaziyorsa yenilemeyi ertele — cumlenin ortasinda
// sayfanin gitmesi en sinir bozucu davranis olurdu.
(function(){
  const meta=document.querySelector('meta[http-equiv="refresh"]');
  if(!meta)return;
  const sn=parseInt(meta.content,10)||60;
  let kalan=sn*1000, sonYazim=0;
  q.addEventListener('input',()=>{sonYazim=Date.now();});
  setInterval(()=>{
    kalan-=1000;
    if(kalan<=0){
      if(Date.now()-sonYazim<15000){kalan=10000;return;}  // yazim sonrasi 10 sn daha bekle
      kaydet(); location.reload();
    }
  },1000);
  meta.remove();
})();
document.querySelectorAll('th[data-k]').forEach((th,i)=>{
  th.addEventListener('click',()=>{
    const tb=document.querySelector('tbody'), rows=[...tb.rows];
    const asc=th.dataset.asc!=='1'; th.dataset.asc=asc?'1':'0';
    rows.sort((a,b)=>{
      const x=a.cells[i].dataset.v??a.cells[i].textContent, y=b.cells[i].dataset.v??b.cells[i].textContent;
      const nx=parseFloat(x), ny=parseFloat(y);
      const c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y),'tr');
      return asc?c:-c;
    });
    rows.forEach(r=>tb.appendChild(r));
  });
});
"""


LOGIN_PAGE = """<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Giriş — Yurt İnternet Durumu</title>
<script>__TEMA_ON__</script>
<style>
/* Koyu varsayılan; açık tema yalnızca kullanıcı seçtiyse (aynı localStorage anahtarı). */
:root{color-scheme:dark;--bg:#0d0d0d;--card:#1a1a19;--fg:#fff;--muted:#898781;
      --line:#2c2c2a;--accent:#3987e5;--err-bg:#3a1c19;--err-fg:#f3b8b1;--err-line:#6b2a24}
:root[data-tema="acik"]{color-scheme:light;--bg:#f9f9f7;--card:#fcfcfb;--fg:#0b0b0b;
      --muted:#52514e;--line:#e4e3dc;--accent:#2a78d6;--err-bg:#fbe6e4;--err-fg:#8a1c14;
      --err-line:#f0b4ae}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
     padding:20px;background:var(--bg);color:var(--fg);
     font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;
     padding:28px;width:100%;max-width:370px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
/* Logo siyah yazı içerdiği için koyu temada okunmaz kalır; her iki temada da
   beyaz bir zemin üzerinde gösterilir, böylece kasıtlı bir levha gibi durur. */
.logo{display:block;background:#fff;border-radius:9px;padding:13px 16px;margin:0 0 20px;
      text-align:center}
.logo img{width:100%;max-width:205px;height:auto;display:inline-block}
h1{font-size:16.5px;margin:0 0 3px;font-weight:650}
.sub{color:var(--muted);font-size:13px;margin:0 0 20px}
label{display:block;font-size:12.5px;font-weight:600;margin:0 0 6px;color:var(--fg)}
input{width:100%;padding:10px 12px;font-size:14px;font-family:inherit;margin-bottom:15px;
      background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:7px}
input:focus{outline:2px solid var(--accent);outline-offset:-1px;border-color:transparent}
button{width:100%;padding:11px;font-size:14px;font-weight:600;font-family:inherit;
       background:var(--accent);color:#fff;border:0;border-radius:7px;cursor:pointer}
button:hover{filter:brightness(1.08)}
.err{background:var(--err-bg);border:1px solid var(--err-line);color:var(--err-fg);
     border-radius:7px;padding:9px 12px;font-size:13px;margin-bottom:16px}
/* Parolada noktalama var; telefonda yazarken görebilmek hata payını düşürüyor. */
.parola-kutu{position:relative}
.parola-kutu input{padding-right:74px}
.goz{position:absolute;right:7px;top:6px;background:none;border:0;cursor:pointer;
     color:var(--muted);font-size:12px;font-family:inherit;padding:5px 7px}
.goz:hover{color:var(--fg)}
</style>
</head><body>
  <form class="box" method="POST" action="/login">
    <span class="logo"><img src="__LOGO__" alt="Piramit Bilgisayar"></span>
    <h1>Yurt İnternet Durumu</h1>
    <p class="sub">Devam etmek için giriş yapın.</p>
    __ERROR__
    <!-- autocapitalize/autocorrect kapalı: telefon klavyeleri ilk harfi büyütüp
         "Yurtnet" gönderiyor ve doğru parolayla bile giriş reddediliyordu. -->
    <label for="u">Kullanıcı adı</label>
    <input id="u" name="username" autocomplete="username" autofocus required
           autocapitalize="none" autocorrect="off" spellcheck="false" inputmode="text">
    <label for="p">Parola</label>
    <div class="parola-kutu">
      <input id="p" name="password" type="password" autocomplete="current-password" required
             autocapitalize="none" autocorrect="off" spellcheck="false">
      <button type="button" id="goster" class="goz" aria-label="Parolayı göster">Göster</button>
    </div>
    <button type="submit">Giriş yap</button>
  </form>
<script>
(function(){
  var p=document.getElementById('p'), b=document.getElementById('goster');
  if(!p||!b)return;
  b.addEventListener('click',function(){
    var gizli = p.type==='password';
    p.type = gizli ? 'text' : 'password';
    b.textContent = gizli ? 'Gizle' : 'Göster';
    p.focus();
  });
})();
</script>
</body></html>
"""


def render_login(error: str = "") -> str:
    block = f'<div class="err">{esc(error)}</div>' if error else ""
    return (
        LOGIN_PAGE.replace("__ERROR__", block)
        .replace("__LOGO__", LOGO_DATA_URI)
        .replace("__TEMA_ON__", pages.TEMA_ONYUKLEME)
    )


def render(
    snapshots: list[HostSnapshot],
    findings_by_host: dict[str, list[Finding]],
    regional: list[Finding],
    config: dict[str, Any],
) -> str:
    refresh = config["poll"]["dashboard_refresh_minutes"] * 60
    rows = sorted(
        snapshots,
        key=lambda s: (
            -_worst_rank(findings_by_host.get(s.hostid, [])),
            s.region,
            s.name.lower(),
        ),
    )

    counts = {"critical": 0, "warning": 0, "info": 0, "ok": 0}
    for snap in snapshots:
        counts[_worst_severity(findings_by_host.get(snap.hostid, []))] += 1
        _HOST_ADLARI[snap.hostid] = (snap.name, snap.host)

    regions = sorted({s.region for s in snapshots})
    banners = "".join(
        f'<div class="banner"><strong>{esc(f.title)}</strong><br>{esc(f.action)}</div>'
        for f in regional
    )

    govde = f"""<meta http-equiv="refresh" content="{refresh}">
<h1>Yurt İnternet Durumu</h1>
<p class="alt">Son güncelleme: {esc(fmt_time(time.time()))} · {len(snapshots)} yurt ·
  tablo {config['poll']['dashboard_refresh_minutes']} dakikada bir yenilenir</p>
{banners}
{pages.kpi([
    (str(counts['critical']), 'Kritik', ''),
    (str(counts['warning']), 'Uyarı', ''),
    (str(counts['info']), 'Bilgi', ''),
    (str(counts['ok']), 'Normal', ''),
    (str(len(regions)), 'Bölge', ''),
])}
<div class="tools">
  <input id="q" placeholder="Yurt adı, bölge veya IP ara…">
  <select id="rg"><option value="">Tüm bölgeler</option>
    {"".join(f'<option>{esc(r)}</option>' for r in regions)}
  </select>
  <select id="st"><option value="">Tüm durumlar</option>
    <option value="critical">Kritik</option><option value="warning">Uyarı</option>
    <option value="info">Bilgi</option><option value="ok">Normal</option>
  </select>
</div>
<p class="alt"><span id="count">{len(snapshots)}</span> kayıt gösteriliyor</p>
<div class="wrap"><table>
<thead><tr>
  <th data-k>Durum</th><th data-k>Yurt</th><th data-k>Bölge</th><th data-k>Gecikme</th>
  <th data-k>Kayıp</th><th data-k>İndirme</th><th data-k>Yükleme</th><th data-k>Doluluk</th>
  <th data-k>WAN</th><th data-k>Çalışma süresi</th><th data-k>Ön tanı</th>
</tr></thead>
<tbody>
{"".join(_row(s, findings_by_host.get(s.hostid, []), config) for s in rows)}
</tbody></table></div>
<script>{JS}</script>"""

    return pages.shell(
        baslik="Yurt İnternet Durumu",
        aktif="/",
        govde=govde,
        logo=LOGO_DATA_URI,
        cikis=bool((config["dashboard"].get("auth") or {}).get("enabled")),
        ek_css=CSS,
    )


def _row(snap: HostSnapshot, findings: list[Finding], config: dict[str, Any]) -> str:
    severity = _worst_severity(findings)
    color = SEVERITY_COLOR[severity]
    label = {"critical": "KRİTİK", "warning": "UYARI", "info": "BİLGİ", "ok": "NORMAL"}[severity]
    thresholds = config["thresholds"]
    rank = {"ok": 0, "info": 1, "warning": 2, "critical": 3}[severity]

    if snap.util_pct is None:
        util_cell = '<span class="dim" title="Hat kapasitesi henüz bilinmiyor">—</span>'
    else:
        tahmin = " ~" if snap.capacity_estimated else ""
        util_cell = f"{fmt_pct(snap.util_pct, 0)}{tahmin}"

    wan_cell = f'{esc(snap.wan)}' if snap.wan else '<span class="dim">—</span>'
    uptime_cell = (
        fmt_duration(snap.uptime_seconds)
        if snap.uptime_seconds
        else '<span class="dim">—</span>'
    )

    if findings:
        top = findings[0]
        remote = "uzaktan" if top.remote_fixable else "yerinde"
        diagnosis = (
            f'<strong>{esc(top.title)}</strong><br>{esc(top.detail)}'
            f'<span class="act">→ {esc(top.action)} <em>({remote})</em></span>'
        )
        if len(findings) > 1:
            others = ", ".join(esc(f.title) for f in findings[1:])
            diagnosis += f'<span class="act">Ayrıca: {others}</span>'
    else:
        diagnosis = '<span class="dim">Sorun tespit edilmedi</span>'

    diagnosis += _planli_dugme(snap, findings)

    search = f"{snap.name} {snap.host} {snap.region} {snap.address}".lower()
    return f"""<tr data-search="{esc(search)}" data-region="{esc(snap.region)}" data-sev="{severity}">
<td data-v="{rank}">
  <span class="badge" style="color:{color};background:{color}22">{label}</span></td>
<td><div class="name">{esc(snap.name)}</div><div class="dim" style="font-size:11.5px">{esc(snap.address)}</div></td>
<td>{esc(snap.region)}</td>
<td class="num {_cls(snap.latency_ms, thresholds['latency_warn_ms'], thresholds['latency_crit_ms'])}"
    data-v="{snap.latency_ms if snap.latency_ms is not None else -1}">{fmt_ms(snap.latency_ms)}</td>
<td class="num {_cls(snap.loss_pct, thresholds['loss_warn'], thresholds['loss_crit'])}"
    data-v="{snap.loss_pct if snap.loss_pct is not None else -1}">{fmt_pct(snap.loss_pct)}</td>
<td class="num" data-v="{snap.in_bps or 0}">{fmt_bps(snap.in_bps)}</td>
<td class="num" data-v="{snap.out_bps or 0}">{fmt_bps(snap.out_bps)}</td>
<td class="num {_cls(snap.util_pct, thresholds['bandwidth_util_warn'], thresholds['bandwidth_util_crit'])}"
    data-v="{snap.util_pct if snap.util_pct is not None else -1}">{util_cell}</td>
<td class="num">{wan_cell}</td>
<td class="num" data-v="{snap.uptime_seconds or -1}">{uptime_cell}</td>
<td class="diag">{diagnosis}</td>
</tr>"""


def _planli_dugme(snap: HostSnapshot, findings: list[Finding]) -> str:
    """Kopuk yurtlar için 'bilinçli kapalı' işaretleme düğmesi.

    Yalnızca erişilemeyen yurtlarda gösterilir: çalışan bir yurdu kapalı
    işaretlemenin anlamı yok, düğme her satırda dursa tabloyu kalabalıklaştırır.
    """
    planli = any(f.code == "PLANNED_DOWN" for f in findings)
    if planli:
        return f"""<form class="pl" method="POST" action="/planli">
  <input type="hidden" name="hostid" value="{esc(snap.hostid)}">
  <input type="hidden" name="islem" value="kaldir">
  <button class="geri" type="submit">Arıza olarak işaretle</button>
</form>"""

    kopuk = snap.reachable is False or not snap.has_data
    if not kopuk:
        return ""
    return f"""<form class="pl" method="POST" action="/planli">
  <input type="hidden" name="hostid" value="{esc(snap.hostid)}">
  <input type="hidden" name="islem" value="isaretle">
  <input type="text" name="kapatma_sebebi" placeholder="sebep (isteğe bağlı)" maxlength="90"
         autocomplete="off" spellcheck="false">
  <button type="submit">Bilinçli kapalı</button>
</form>"""


def _cls(value: float | None, warn: float, crit: float) -> str:
    if value is None:
        return "dim"
    if value >= crit:
        return "crit"
    if value >= warn:
        return "warn"
    return ""


def _worst_severity(findings: list[Finding]) -> str:
    for level in ("critical", "warning", "info"):
        if any(f.severity == level for f in findings):
            return level
    return "ok"


def _worst_rank(findings: list[Finding]) -> int:
    return {"ok": 0, "info": 1, "warning": 2, "critical": 3}[_worst_severity(findings)]


def write(html_text: str, output_file: str) -> None:
    path = Path(output_file)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(html_text, encoding="utf-8")
    tmp.replace(path)  # yarım dosya servis edilmesin diye atomik değiştirme


def serve(config: dict[str, Any], store=None, yeniden_ciz=None) -> threading.Thread | None:
    """dashboard.html'i basit bir HTTP sunucusuyla yayınlar (arka plan thread)."""
    dashboard_config = config["dashboard"]
    if not dashboard_config.get("enabled"):
        return None

    output_path = Path(dashboard_config["output_file"])
    directory = str(output_path.parent)

    # URL yolu -> diskteki dosya. Üç sekme üç ayrı sayfadır.
    SAYFALAR = {
        "/": output_path.name,
        "/index.html": output_path.name,
        "/teknik": TEKNIK_DOSYA,
        "/ekran": EKRAN_DOSYA,
        "/yonetici": YONETICI_DOSYA,
    }

    auth_config = dashboard_config.get("auth") or {}
    auth_enabled = bool(auth_config.get("enabled")) and bool(auth_config.get("password"))
    username = auth_config.get("username") or "yurtnet"
    password = auth_config.get("password") or ""
    # 0 = oturum dolmasın. Pano duvardaki ekranda da açık duruyor ve süre
    # dolduğunda ekran giriş sayfasına düşüyordu; kimse başında olmadığı için
    # de öyle kalıyordu. Çıkış yapmak isteyen "Çıkış yap" düğmesini kullanır.
    gun = int(auth_config.get("session_days", 0))
    lifetime = gun * 86400 if gun > 0 else 10 * 365 * 86400
    secret = (
        auth.load_or_create_secret(output_path.parent / ".session_secret")
        if auth_enabled
        else b""
    )

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        # ------------------------------------------------------------ oturum

        def _session_user(self) -> str | None:
            if not auth_enabled:
                return username
            raw = self.headers.get("Cookie", "")
            for part in raw.split(";"):
                name, _, value = part.strip().partition("=")
                if name == auth.COOKIE_NAME:
                    return auth.verify(secret, value)
            return None

        def _https_mi(self) -> bool:
            """İstek tarayıcıya HTTPS olarak mı gitti.

            Uygulama düz HTTP konuşuyor; TLS'i önündeki nginx sonlandırıyor.
            Bu yüzden soket değil, proxy'nin koyduğu başlık belirleyici.
            """
            return (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"

        def _cerez(self, govde: str) -> str:
            """Set-Cookie değerini üretir; HTTPS arkasındaysa Secure ekler.

            Secure'u koşulsuz eklemek olmaz: düz HTTP ile açılan kurulumlarda
            tarayıcı çerezi hiç saklamaz ve giriş sonsuz döngüye girer.
            """
            return govde + ("; Secure" if self._https_mi() else "")

        def _send_html(self, body: str, status: int = 200, cookie: str | None = None) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(payload)

        def _redirect(self, location: str, cookie: str | None = None) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()

        # ------------------------------------------------------------- HTTP

        def do_GET(self):  # noqa: N802 — stdlib arayüzü
            if self.path.startswith("/logout"):
                return self._redirect(
                    "/login",
                    self._cerez(f"{auth.COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"),
                )

            if self._session_user() is None:
                return self._send_html(render_login())

            if self.path.startswith("/login"):
                return self._redirect("/")
            if self.path.startswith("/pdf/aylik"):
                return self._pdf_indir()
            if self.path.rstrip("/") == "/ayarlar":
                return self._ayarlar_goster()
            if self.path.split("?")[0].rstrip("/") == "/trafik":
                return self._trafik()
            hedef = SAYFALAR.get(self.path.rstrip("/") or "/")
            if hedef:
                if not (output_path.parent / hedef).exists():
                    return self._send_html(
                        "<p style='font-family:sans-serif;padding:24px'>Bu sayfa henüz "
                        "oluşturulmadı; ilk kontrol turu tamamlanınca hazır olacak.</p>",
                        status=503,
                    )
                self.path = "/" + hedef
            return super().do_GET()

        def do_HEAD(self):  # noqa: N802
            if self._session_user() is None:
                return self._send_html("", status=401)
            hedef = SAYFALAR.get(self.path.rstrip("/") or "/")
            if hedef:
                self.path = "/" + hedef
            return super().do_HEAD()

        def _form_oku(self) -> dict[str, list[str]]:
            length = min(int(self.headers.get("Content-Length") or 0), 4096)
            return urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))

        def do_POST(self):  # noqa: N802
            if self.path.startswith("/planli"):
                if self._session_user() is None:
                    return self._send_html(render_login(), status=401)
                return self._planli()

            if self.path.startswith("/ayarlar"):
                if self._session_user() is None:
                    return self._send_html(render_login(), status=401)
                return self._ayarlar_kaydet()

            if self.path.startswith("/kapat"):
                if self._session_user() is None:
                    return self._send_html(render_login(), status=401)
                return self._kapat()

            if not self.path.startswith("/login"):
                return self._send_html("<p>Bulunamadı</p>", status=404)

            fields = self._form_oku()
            user = (fields.get("username") or [""])[0]
            given = (fields.get("password") or [""])[0]

            if not auth.check_password(username, password, user, given):
                # Kaba kuvvet denemesini yavaşlatmak için kısa gecikme.
                time.sleep(0.7)
                log.warning("Dashboard giriş denemesi başarısız (%s)", self.client_address[0])
                return self._send_html(
                    render_login("Kullanıcı adı veya parola hatalı."), status=401
                )

            token = auth.issue(secret, username, lifetime)
            return self._redirect(
                "/",
                self._cerez(
                    f"{auth.COOKIE_NAME}={token}; Path=/; Max-Age={lifetime}; HttpOnly; SameSite=Lax"
                ),
            )

        def _pdf_indir(self) -> None:
            """PDF'i anlık üretip indirme olarak sunar.

            Diske yazılıp statik sunulsa dosya bayatlar; üretim ~0.3 sn sürüyor,
            her istekte taze üretmek daha basit ve doğru.
            """
            if store is None:
                return self._send_html("<p>Rapor üretilemiyor.</p>", status=503)
            # Yalnızca aylık rapor var; haftalık PDF kaldırıldı.
            try:
                from . import pdf as pdf_uretici

                icerik = pdf_uretici.uret(store, config, 30)
            except Exception:
                log.exception("PDF üretilemedi")
                return self._send_html(
                    "<p style='font-family:sans-serif;padding:24px'>PDF üretilemedi. "
                    "Sunucu günlüğüne bakın.</p>", status=500
                )
            dosya = f"yurtnet-aylik-rapor-{time.strftime('%Y-%m-%d')}.pdf"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{dosya}"')
            self.send_header("Content-Length", str(len(icerik)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(icerik)

        def _kapat(self) -> None:
            """Teknik servis raporundaki bir kaydı kapatır veya kapatmayı geri alır."""
            if store is None:
                return self._redirect("/teknik")
            a = self._form_oku()
            bolum = (a.get("bolum") or [""])[0]
            anahtar = (a.get("anahtar") or [""])[0]
            if bolum not in ("zabbix", "tekrar", "analiz") or not anahtar:
                return self._redirect("/teknik")

            if (a.get("islem") or [""])[0] == "geri":
                store.kapatmayi_geri_al(bolum, anahtar)
                log.info("Kayıt yeniden açıldı: %s/%s", bolum, anahtar)
            else:
                store.kapat(bolum, anahtar, (a.get("baslik") or [""])[0])
                log.info("Kayıt kapatıldı: %s/%s", bolum, anahtar)

            # Sayfayı hemen tazele; yoksa kullanıcı düğmeye basıp hiçbir şey
            # olmamış gibi görür ve düğmenin çalışmadığını sanır.
            try:
                from . import servis
                from .brand import LOGO_DATA_URI as _logo

                html = servis.sayfa(store, config, _logo)
                write(html, str(output_path.parent / TEKNIK_DOSYA))
            except Exception:
                log.exception("Teknik sayfa tazelenemedi")
            return self._redirect("/teknik")

        def _trafik(self) -> None:
            """Trafik grafikleri. Zabbix geçmişi istek anında çekilir — her turda
            çekmek gereksiz yük olurdu, sayfa nadiren açılıyor."""
            from . import trafik

            sorgu = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                saat = int((sorgu.get("saat") or ["6"])[0])
            except ValueError:
                saat = 6
            try:
                html = trafik.sayfa(
                    config, LOGO_DATA_URI, (sorgu.get("yurt") or [None])[0], saat
                )
            except Exception:
                log.exception("Trafik grafiği üretilemedi")
                return self._send_html(
                    "<p style='font-family:sans-serif;padding:24px'>Grafik üretilemedi. "
                    "Sunucu günlüğüne bakın.</p>", status=500
                )
            return self._send_html(html)

        # ----------------------------------------------------------- ayarlar

        def _ayarlar_goster(self, mesaj: tuple[str, str] | None = None) -> None:
            from . import ayarlar as ayar_deposu
            from . import ayarlar_sayfa

            return self._send_html(
                ayarlar_sayfa.sayfa(
                    config, LOGO_DATA_URI, mesaj, ayar_deposu.eksikler(config)
                )
            )

        def _ayarlar_kaydet(self) -> None:
            """Formu doğrular, diske yazar ve çalışan yapılandırmaya uygular."""
            from . import ayarlar as ayar_deposu
            from . import ayarlar_sayfa
            from . import notify

            alanlar = self._form_oku()
            email, rapor, hata = ayarlar_sayfa.formdan_oku(alanlar, config["email"])
            if hata:
                return self._ayarlar_goster(("kotu", esc(hata)))

            try:
                ayar_deposu.kaydet(config, email, rapor)
            except OSError as exc:
                log.exception("Mail ayarları yazılamadı")
                return self._ayarlar_goster(
                    ("kotu", f"Ayarlar diske yazılamadı: {esc(str(exc))}")
                )

            # Çalışan sürecin sözlüğünü yerinde günceller: bir sonraki mail
            # yeni ayarlarla gider, servisi yeniden başlatmak gerekmez.
            config["email"].update(email)
            config["report"].update(rapor)
            log.info("Mail ayarları panodan güncellendi (%s).", self.client_address[0])

            if (alanlar.get("islem") or [""])[0] != "test":
                return self._ayarlar_goster(("iyi", "Ayarlar kaydedildi."))

            if not config["email"].get("enabled"):
                return self._ayarlar_goster(
                    ("uyari", "Ayarlar kaydedildi ama mail gönderimi kapalı, "
                              "test maili gönderilmedi.")
                )
            gonderildi = notify.send_mail(
                config,
                "[TEST] Yurt İnternet İzleme",
                "<p style='font-family:sans-serif;font-size:14px'>Bu bir test mesajıdır. "
                "SMTP ayarlarınız çalışıyor.</p>",
            )
            if gonderildi:
                alicilar = ", ".join(config["email"]["recipients"])
                return self._ayarlar_goster(
                    ("iyi", f"Ayarlar kaydedildi, test maili gönderildi: {esc(alicilar)}")
                )
            return self._ayarlar_goster(
                ("kotu", "Ayarlar kaydedildi ama test maili gönderilemedi. "
                         "Sunucu adresi, port, şifreleme kipi ve parolayı kontrol edin; "
                         "ayrıntılı hata sunucu günlüğünde.")
            )

        def _planli(self) -> None:
            """'Bilinçli kapalı' işaretini açar/kapatır ve tabloyu hemen tazeler."""
            if store is None:
                return self._redirect("/")
            alanlar = self._form_oku()
            hostid = (alanlar.get("hostid") or [""])[0]
            islem = (alanlar.get("islem") or [""])[0]
            aciklama = (alanlar.get("kapatma_sebebi") or [""])[0].strip()[:90]
            if not hostid:
                return self._redirect("/")

            if islem == "isaretle":
                ad, teknik = _host_adi(hostid)
                store.set_planned(hostid, teknik, ad, aciklama)
                # Kullanıcı "bu kapalılık kasıtlı" diyor; süregelen kesinti
                # geçmişe dönük düzeltilmezse rapor haftalarca yanlış kalır.
                olcum, ariza = store.backfill_current_outage(hostid)
                log.info(
                    "%s bilinçli kapalı işaretlendi%s — %d geçmiş ölçüm ve %d arıza kaydı düzeltildi.",
                    ad or hostid, f" ({aciklama})" if aciklama else "", olcum, ariza,
                )
            else:
                store.clear_planned(hostid)
                log.info("%s için bilinçli kapalı işareti kaldırıldı.", hostid)

            if yeniden_ciz is not None:
                try:
                    yeniden_ciz()
                except Exception:
                    log.exception("Tablo yeniden çizilemedi.")
            return self._redirect("/")

        def log_message(self, *_args):  # erişim loglarını bastır
            pass

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = Server((dashboard_config["bind"], dashboard_config["port"]), Handler)
    thread = threading.Thread(target=httpd.serve_forever, name="dashboard-http", daemon=True)
    thread.start()
    log.info(
        "Dashboard yayında: http://%s:%s/ (parola korumalı: %s)",
        dashboard_config["bind"],
        dashboard_config["port"],
        "evet" if auth_enabled else "HAYIR",
    )
    if not auth_enabled and dashboard_config["bind"] not in ("127.0.0.1", "localhost"):
        log.warning(
            "Dashboard ağa açık ve parolasız! config.yaml > dashboard.auth ayarını doldurun."
        )
    return thread
