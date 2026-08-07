"""Panodaki mail ayarları sayfası.

Ayarların sunucuya SSH ile girip config.yaml düzenlemeden değiştirilebilmesi
için var. Yalnızca mail bölümünü kapsar: eşikler, Zabbix bilgisi ve pano
parolası hâlâ config.yaml'dan yönetilir — onlar nadiren değişir ve yanlış
girildiğinde uygulamayı büsbütün durdurabilir.
"""

from __future__ import annotations

from typing import Any

from . import pages
from .render import esc

AYAR_CSS = """
.ayar-form{max-width:640px}
.ayar-satir{margin-bottom:17px}
.ayar-satir label{display:block;font-size:12.5px;font-weight:600;margin-bottom:6px}
.ayar-satir .yardim{font-size:11.5px;color:var(--muted);margin:5px 0 0;line-height:1.5}
.ayar-satir input[type=text],.ayar-satir input[type=password],
.ayar-satir input[type=number],.ayar-satir textarea,.ayar-satir select{
  width:100%;padding:9px 11px;font-size:13.5px;font-family:inherit;
  background:var(--plane);color:var(--ink);border:1px solid var(--line);border-radius:7px}
.ayar-satir textarea{min-height:74px;resize:vertical;line-height:1.6}
.ayar-satir input:focus,.ayar-satir textarea:focus,.ayar-satir select:focus{
  outline:2px solid var(--seri);outline-offset:-1px;border-color:transparent}
.ayar-ikili{display:grid;grid-template-columns:1fr 150px;gap:14px}
.onay{display:flex;align-items:flex-start;gap:9px;font-size:13.5px;line-height:1.5}
.onay input{margin-top:2px;width:16px;height:16px;flex:none}
.dugmeler{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px;padding-top:18px;
  border-top:1px solid var(--line)}
.dugme{font-family:inherit;font-size:13px;font-weight:600;padding:9px 17px;border-radius:7px;
  cursor:pointer;border:1px solid var(--seri);background:var(--seri);color:#fff}
.dugme.ikincil{background:transparent;color:var(--seri)}
.dugme.ikincil:hover{background:var(--seri);color:#fff}
.bildirim{border-radius:9px;padding:12px 15px;margin-bottom:18px;font-size:13.5px;
  line-height:1.55}
.bildirim.iyi{background:rgba(12,163,12,.11);border:1px solid rgba(12,163,12,.35);
  color:var(--iyi-ink)}
.bildirim.kotu{background:rgba(208,59,59,.10);border:1px solid rgba(208,59,59,.35);
  color:var(--kritik-ink)}
.bildirim.uyari{background:rgba(250,178,25,.11);border:1px solid rgba(250,178,25,.35);
  color:var(--uyari-ink)}
"""

# Port seçilince şifreleme kipini otomatik ayarlar: 465 doğrudan SSL, 587
# STARTTLS. Bu ikisinin karıştırılması mailin sessizce gitmemesinin en sık
# sebebi; kullanıcıya soru olarak sormak yerine porttan çıkarılıyor.
AYAR_JS = """
<script>
(function(){
  var port=document.getElementById('smtp_port'), kip=document.getElementById('kip');
  if(!port||!kip) return;
  port.addEventListener('change',function(){
    if(port.value==='465') kip.value='ssl';
    else if(port.value==='587'||port.value==='25') kip.value='starttls';
  });
})();
</script>
"""


def _satir(etiket: str, alan: str, yardim: str = "") -> str:
    y = f'<p class="yardim">{yardim}</p>' if yardim else ""
    return f'<div class="ayar-satir"><label>{esc(etiket)}</label>{alan}{y}</div>'


def _liste(deger: Any) -> str:
    return "\n".join(deger or [])


def sayfa(
    config: dict[str, Any],
    logo: str,
    mesaj: tuple[str, str] | None = None,
    eksikler: list[str] | None = None,
) -> str:
    """Ayar formunu üretir. mesaj = (durum, metin) — kaydetme sonrası geri bildirim."""
    mail = config["email"]
    rapor = config["report"]

    kip = "ssl" if mail.get("use_ssl") else ("starttls" if mail.get("use_tls") else "yok")
    parola_var = bool(mail.get("password"))

    bildirimler = []
    if mesaj:
        durum, metin = mesaj
        bildirimler.append(f'<div class="bildirim {durum}">{metin}</div>')
    if eksikler:
        bildirimler.append(
            '<div class="bildirim uyari"><strong>Mail gönderimi şu an kapalı.</strong> '
            f"Eksik olan: {esc(', '.join(eksikler))}. Doldurup kaydedince açılır.</div>"
        )

    # Form tek <form>, üç kart hâlinde gösteriliyor: hesap bilgisi bir kez
    # girilir, alıcı listeleri ise ayrı ayrı ve daha sık düzenlenir.
    hesap = f"""
{_satir("", f'''<div class="onay">
  <input type="checkbox" id="enabled" name="enabled" value="1" {"checked" if mail.get("enabled") else ""}>
  <label for="enabled" style="font-weight:600;margin:0">Mail gönderimi açık</label></div>''')}

<div class="ayar-ikili">
  {_satir("Sunucu adresi (SMTP)",
          f'<input type="text" name="smtp_host" value="{esc(mail.get("smtp_host") or "")}" '
          'placeholder="mail.ornek.com.tr" spellcheck="false">')}
  {_satir("Port",
          f'''<select id="smtp_port" name="smtp_port">
  <option value="465" {"selected" if int(mail.get("smtp_port") or 0) == 465 else ""}>465</option>
  <option value="587" {"selected" if int(mail.get("smtp_port") or 0) == 587 else ""}>587</option>
  <option value="25" {"selected" if int(mail.get("smtp_port") or 0) == 25 else ""}>25</option>
</select>''')}
</div>

{_satir("Şifreleme", f'''<select id="kip" name="kip">
  <option value="ssl" {"selected" if kip == "ssl" else ""}>SSL / TLS (genelde port 465)</option>
  <option value="starttls" {"selected" if kip == "starttls" else ""}>STARTTLS (genelde port 587)</option>
  <option value="yok" {"selected" if kip == "yok" else ""}>Şifreleme yok</option>
</select>''', "Port seçince bu alan kendiliğinden ayarlanır. Yanlış seçim, mailin hata vermeden gitmemesinin en sık sebebidir.")}

{_satir("Kullanıcı adı",
        f'<input type="text" name="username" value="{esc(mail.get("username") or "")}" '
        'spellcheck="false" autocapitalize="none">',
        "Genelde mail adresinin tamamı.")}

{_satir("Parola",
        '<input type="password" name="password" placeholder="'
        + ("değiştirmek için yazın — boş bırakılırsa mevcut parola korunur" if parola_var
           else "hesabın parolası")
        + '" autocomplete="new-password">',
        "Kayıtlı parola hiçbir zaman ekranda gösterilmez.")}

{_satir("Gönderen adresi",
        f'<input type="text" name="sender" value="{esc(mail.get("sender") or "")}" '
        'placeholder="yurtnet@ornek.com.tr" spellcheck="false" autocapitalize="none">',
        "Maillerin 'kimden' alanında görünecek adres. Çoğu sunucu bunun kullanıcı adıyla aynı olmasını ister.")}
"""

    yonetici = f"""
{_satir("Bu adreslere gönderilecek",
        f'<textarea name="monthly_recipients" spellcheck="false" '
        f'placeholder="mudur@ornek.com.tr">{esc(_liste(rapor.get("monthly_recipients")))}</textarea>',
        "Her satıra bir adres.")}

{_satir("", f'''<div class="onay">
  <input type="checkbox" id="monthly_enabled" name="monthly_enabled" value="1"
         {"checked" if rapor.get("monthly_enabled") else ""}>
  <label for="monthly_enabled" style="font-weight:600;margin:0">Her ayın 1'inde saat 09:00'da otomatik gönder</label></div>''',
        "Biten ayın özeti, PDF eki olarak gider. Kapatılırsa rapor yalnızca panodan indirilir.")}
"""

    seviye = mail.get("min_severity") or "critical"
    sure_dk = int(mail.get("min_duration_minutes") or 5)
    soguma_dk = int(mail.get("alert_cooldown_minutes") or 60)
    teknik = f"""
{_satir("Bu adreslere gönderilecek",
        f'<textarea name="recipients" spellcheck="false" '
        f'placeholder="servis@ornek.com.tr">{esc(_liste(mail.get("recipients")))}</textarea>',
        "Her satıra bir adres. Hem arıza bildirimleri hem haftalık teknik rapor bu listeye gider.")}

{_satir("Hangi arızalar maillensin", f'''<select name="min_severity">
  <option value="critical" {"selected" if seviye == "critical" else ""}>Yalnız kritik — internet kesintisi, hat kopukluğu</option>
  <option value="warning" {"selected" if seviye == "warning" else ""}>Kritik + uyarı — yavaşlık, hat doluluğu, cihaz yeniden başlaması</option>
  <option value="info" {"selected" if seviye == "info" else ""}>Hepsi — izleme eksikleri dâhil</option>
</select>''',
        f"Bir arıza {sure_dk} dakikadan uzun sürmeden mail gitmez; kendiliğinden düzelen kısa "
        f"dalgalanmalar bildirilmez. Aynı arıza için {soguma_dk} dakika içinde ikinci mail atılmaz.")}

{_satir("", f'''<div class="onay">
  <input type="checkbox" id="send_recovery" name="send_recovery" value="1"
         {"checked" if mail.get("send_recovery") else ""}>
  <label for="send_recovery" style="font-weight:600;margin:0">Sorun düzelince &quot;düzeldi&quot; maili de gönder</label></div>''',
        "Kapatılırsa yalnızca arıza maili gider, kapanış bildirimi gitmez.")}

{_satir("", f'''<div class="onay">
  <input type="checkbox" id="weekly_enabled" name="weekly_enabled" value="1"
         {"checked" if rapor.get("weekly_enabled") else ""}>
  <label for="weekly_enabled" style="font-weight:600;margin:0">Haftalık teknik raporu her pazartesi gönder</label></div>''')}
"""

    dugmeler = """
<div class="dugmeler">
  <button class="dugme" type="submit" name="islem" value="kaydet">Kaydet</button>
  <button class="dugme ikincil" type="submit" name="islem" value="test">Kaydet ve test maili gönder</button>
</div>"""

    govde = (
        "".join(bildirimler)
        + '<form class="ayar-form" method="POST" action="/ayarlar" autocomplete="off">'
        + pages.kart(
            "Mail hesabı",
            hesap,
            aciklama=(
                "Bütün bildirimler bu hesap üzerinden gönderilir. Bir kez girilir; "
                "değişiklik kaydedildiği anda geçerli olur, servisi yeniden başlatmaya gerek yok."
            ),
        )
        + pages.kart(
            "Yönetici raporu — kimlere gitsin",
            yonetici,
            aciklama=(
                "Aylık yönetici raporu: grafik ağırlıklı, teknik terim içermez, müşteri "
                "yöneticilerine gösterilebilir. Arıza bildirimleri bu listeye GİTMEZ."
            ),
        )
        + pages.kart(
            "Teknik servis — kimlere gitsin",
            teknik,
            aciklama=(
                "Müdahale eden ekip. Haftalık teknik rapora ek olarak, arıza oluştuğunda ve "
                "düzeldiğinde anlık bildirim bu listeye gider."
            ),
        )
        + dugmeler
        + "</form>"
        + AYAR_JS
    )

    govde += pages.kart(
        "Buradan yönetilmeyenler",
        "<ul style='margin:0;padding-left:19px;line-height:1.8;font-size:13px'>"
        "<li><strong>Zabbix bağlantısı</strong> (adres, token) — <code>config.yaml</code></li>"
        "<li><strong>Pano parolası</strong> — <code>config.yaml</code> veya "
        "<code>YURTNET_DASHBOARD_PASSWORD</code></li>"
        "<li><strong>Arıza eşikleri</strong> (gecikme, kayıp, doluluk yüzdeleri) — <code>config.yaml</code></li>"
        "</ul>",
        aciklama=(
            "Bunlar nadiren değişir ve yanlış girildiğinde uygulamayı büsbütün durdurabilir; "
            "bilerek dosyada bırakıldı."
        ),
    )
    return pages.shell(
        baslik="Mail Ayarları — Yurt İnterneti",
        aktif="/ayarlar",
        govde=govde,
        logo=logo,
        ek_css=AYAR_CSS,
    )


def formdan_oku(alanlar: dict[str, list[str]], mevcut: dict[str, Any]) -> tuple[dict, dict, str]:
    """Form alanlarını ayar sözlüklerine çevirir.

    Dönen: (email ayarları, rapor ayarları, hata mesajı). Hata boşsa geçerli.
    """
    def tek(ad: str, varsayilan: str = "") -> str:
        return (alanlar.get(ad) or [varsayilan])[0].strip()

    def satirlar(ad: str) -> list[str]:
        ham = (alanlar.get(ad) or [""])[0]
        return [s.strip() for s in ham.replace(",", "\n").splitlines() if s.strip()]

    acik = bool(alanlar.get("enabled"))
    kip = tek("kip", "ssl")
    try:
        port = int(tek("smtp_port", "465"))
    except ValueError:
        return {}, {}, "Port bir sayı olmalı."

    email = {
        "enabled": acik,
        "smtp_host": tek("smtp_host"),
        "smtp_port": port,
        "use_ssl": kip == "ssl",
        "use_tls": kip == "starttls",
        "username": tek("username"),
        "sender": tek("sender"),
        "recipients": satirlar("recipients"),
        "min_severity": tek("min_severity", "critical"),
        "send_recovery": bool(alanlar.get("send_recovery")),
    }
    if email["min_severity"] not in ("info", "warning", "critical"):
        email["min_severity"] = "critical"
    # Parola alanı boşsa mevcut parola korunur; kayıtlı parola forma hiç
    # basılmadığı için boş gelmesi "sil" demek değil, "dokunma" demek.
    yeni_parola = tek("password")
    email["password"] = yeni_parola or (mevcut.get("password") or "")

    rapor = {
        "monthly_enabled": bool(alanlar.get("monthly_enabled")),
        "monthly_recipients": satirlar("monthly_recipients"),
        "weekly_enabled": bool(alanlar.get("weekly_enabled")),
        # Haftalık teknik rapor da teknik servis listesine gider; ayrı bir
        # liste tutmak iki yerde güncelleme unutulmasına yol açardı.
        "recipients": satirlar("recipients"),
    }

    if acik:
        eksik = []
        if not email["smtp_host"]:
            eksik.append("sunucu adresi")
        if not email["sender"]:
            eksik.append("gönderen adresi")
        if not email["recipients"]:
            eksik.append("teknik servis alıcıları")
        if eksik:
            return {}, {}, f"Şu alanlar boş bırakılamaz: {', '.join(eksik)}."
        hatali = [a for a in email["recipients"] + rapor["monthly_recipients"] if "@" not in a]
        if hatali:
            return {}, {}, f"Geçersiz adres: {', '.join(hatali[:3])}"

    return email, rapor, ""
