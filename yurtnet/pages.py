"""Üç sayfanın ortak iskeleti: tema, üst sekmeler ve grafik bileşenleri.

Grafikler harici kütüphane olmadan, düz SVG olarak üretilir — sayfa tek parça
kalsın ve kapalı ağdaki bir sunucuda da sorunsuz açılsın diye.

Renk seçimi: tek ölçü gösteren grafiklerde tek hue (mavi) kullanılır; durum
renkleri (iyi/uyarı/kritik) yalnızca durumun kendisi mesajsa devreye girer ve
her zaman yazıyla birlikte gösterilir, renk tek başına anlam taşımaz.
"""

from __future__ import annotations

from .render import esc

# Sekmeler: (yol, başlık)
SEKMELER = [
    ("/", "Yurt İnternet Durumu"),
    ("/teknik", "Teknik Servis Raporu"),
    ("/trafik", "Trafik Grafikleri"),
    ("/yonetici", "Yönetici Raporu"),
]

TEMA = """
/* Koyu tema varsayılan. Açık tema, üst çubuktaki düğmeyle seçilir ve
   tarayıcıda saklanır; işletim sistemi ayarına bakılmaz. */
:root{
  color-scheme:dark;
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --line:#2c2c2a;
  --seri:#3987e5; --seri-soluk:#184f95;
  --iyi:#0ca30c; --uyari:#fab219; --ciddi:#ec835a; --kritik:#d03b3b;
  --uyari-ink:#fab219; --kritik-ink:#e66767; --iyi-ink:#0ca30c;
  --golge:none;
}
:root[data-tema="acik"]{
  color-scheme:light;
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --line:#e4e3dc;
  --seri:#2a78d6; --seri-soluk:#cde2fb;
  --uyari-ink:#8a5d00; --kritik-ink:#a32a2a; --iyi-ink:#046304;
  --golge:0 1px 2px rgba(11,11,11,.04);
}
*{box-sizing:border-box}
body{margin:0;background:var(--plane);color:var(--ink);
     font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:14px;
     -webkit-text-size-adjust:100%}
a{color:inherit}

/* ---- üst çubuk ve sekmeler ---- */
.ust{background:var(--surface);border-bottom:1px solid var(--line);
     padding:0 18px;position:sticky;top:0;z-index:10}
.ust-ic{max-width:1180px;margin:0 auto;display:flex;align-items:center;
        justify-content:space-between;gap:16px;flex-wrap:wrap}
.marka{display:flex;align-items:center;gap:10px;padding:11px 0}
.marka img{height:26px;width:auto;display:block;background:#fff;border-radius:5px;padding:3px 6px}
.sekmeler{display:flex;gap:2px;overflow-x:auto;scrollbar-width:none}
.sekmeler::-webkit-scrollbar{display:none}
.sekme{padding:13px 14px 11px;font-size:13.5px;font-weight:550;color:var(--ink2);
       text-decoration:none;border-bottom:2px solid transparent;white-space:nowrap}
.sekme:hover{color:var(--ink)}
.sekme.aktif{color:var(--seri);border-bottom-color:var(--seri)}
.tema-dugme{font-size:15px;line-height:1;color:var(--muted);background:var(--surface);
       border:1px solid var(--line);border-radius:6px;padding:5px 9px;cursor:pointer;
       font-family:inherit}
.tema-dugme:hover{color:var(--ink);border-color:var(--axis)}
.tema-dugme.aktif-ayar{color:var(--ink);border-color:var(--axis)}
.cikis{font-size:12.5px;color:var(--muted);text-decoration:none;
       border:1px solid var(--line);border-radius:6px;padding:5px 11px;white-space:nowrap}
.cikis:hover{color:var(--ink)}

/* ---- yerleşim ---- */
.govde{max-width:1180px;margin:0 auto;padding:24px 18px 48px}
h1{font-size:24px;margin:0 0 5px;font-weight:660;letter-spacing:-.015em}
h2{font-size:15px;margin:0;font-weight:620;letter-spacing:-.005em}
.alt{color:var(--muted);font-size:13px;margin:0 0 22px;line-height:1.55}
.kart{background:var(--surface);border:1px solid var(--line);border-radius:12px;
      padding:18px 20px 20px;margin-bottom:16px;box-shadow:var(--golge)}
.kart-bas{margin-bottom:16px}
.kart-ac{color:var(--muted);font-size:12.5px;line-height:1.55;margin:5px 0 0;max-width:62ch}
.izgara{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}

/* ---- KPI ---- */
.kpi{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));margin-bottom:18px}
.kpi .k{background:var(--surface);border:1px solid var(--line);border-radius:12px;
        padding:17px 18px 18px;box-shadow:var(--golge);
        display:flex;flex-direction:column}
.kpi .e{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;
        font-weight:600;margin-bottom:9px}
.kpi .d{font-size:30px;font-weight:680;line-height:1;letter-spacing:-.025em}
.kpi .k.one .d{font-size:42px}
.kpi .n{font-size:12px;color:var(--ink2);margin-top:9px;line-height:1.5}
.kpi .k.one{grid-column:span 1}
/* Karşılaştırma satırı: rakamın iyi mi kötü mü olduğunu renk DEĞİL yazı söyler;
   renk yalnızca destekler (ok işareti + "arttı/azaldı" kelimesi her zaman var). */
.delta{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;
       margin-top:8px;padding:3px 9px;border-radius:14px;line-height:1.4}
.delta.iyi{color:var(--iyi-ink);background:rgba(12,163,12,.12)}
.delta.kotu{color:var(--kritik-ink);background:rgba(208,59,59,.12)}
.delta.notr{color:var(--muted);background:rgba(137,135,129,.13);font-weight:500}

/* ---- rozet listesi (etkilenen yurtlar gibi kısa listeler) ---- */
.rozetler{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.yurt-rozet{display:inline-flex;align-items:center;gap:6px;font-size:12px;
            border:1px solid var(--line);border-radius:20px;padding:4px 11px 4px 8px;
            background:var(--plane);white-space:nowrap}
.yurt-rozet .nokta{width:7px;height:7px;border-radius:50%;flex:none}

/* ---- tablo ---- */
.sar{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:10.5px;color:var(--muted);text-transform:uppercase;
   letter-spacing:.05em;padding:7px 9px;border-bottom:1px solid var(--axis);font-weight:600;
   white-space:nowrap}
td{padding:8px 9px;border-bottom:1px solid var(--line);font-size:13px;vertical-align:middle}
tr:last-child td{border-bottom:none}
.sayi{font-variant-numeric:tabular-nums;white-space:nowrap}
.sonuk{color:var(--muted)}
.bos{color:var(--muted);font-size:13px;margin:0}

/* ---- durum rozeti (renk asla tek başına anlam taşımaz, yazı hep var) ---- */
.rozet{display:inline-block;padding:2px 9px;border-radius:11px;font-size:11px;
       font-weight:600;white-space:nowrap}

/* ---- ölçü çubuğu (tablo içi) ---- */
.olcu{display:flex;align-items:center;gap:8px}
.olcu .yol{flex:1;min-width:52px;height:8px;border-radius:4px;background:var(--seri-soluk);overflow:hidden}
.olcu .dolu{height:100%;border-radius:4px;background:var(--seri)}

svg{display:block;max-width:100%;height:auto}
.ipucu{font-size:11.5px;color:var(--muted);margin:12px 0 0;line-height:1.5}
.grafik{overflow-x:auto;padding-bottom:2px}

/* ---- PDF indirme düğmesi ---- */
.pdf-dugme{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;font-weight:600;
     color:var(--seri);text-decoration:none;border:1px solid var(--seri);border-radius:7px;
     padding:7px 14px;white-space:nowrap;background:transparent}
.pdf-dugme:hover{background:var(--seri);color:#fff}
.baslik-sirasi{display:flex;justify-content:space-between;align-items:flex-start;
     gap:14px;flex-wrap:wrap}
"""


# Sayfa çizilmeden önce çalışır: seçili tema stil uygulanmadan ayarlanmazsa
# koyu modu seçmiş kullanıcı her yenilemede bir anlığına beyaz ekran görür.
TEMA_ONYUKLEME = (
    "try{var t=localStorage.getItem('yurtnet.tema');"
    "if(t==='acik')document.documentElement.setAttribute('data-tema','acik');}catch(e){}"
)

TEMA_JS = """
(function(){
  var d=document.documentElement, b=document.getElementById('tema');
  if(!b)return;
  function goster(){ b.textContent = d.getAttribute('data-tema')==='acik' ? '☾' : '☀'; }
  goster();
  b.addEventListener('click',function(){
    var acik = d.getAttribute('data-tema')==='acik';
    if(acik){ d.removeAttribute('data-tema'); } else { d.setAttribute('data-tema','acik'); }
    try{ localStorage.setItem('yurtnet.tema', acik?'koyu':'acik'); }catch(e){}
    goster();
  });
})();
"""


def shell(
    *, baslik: str, aktif: str, govde: str, logo: str, cikis: bool = True, ek_css: str = ""
) -> str:
    """Tam bir HTML sayfası üretir.

    charset bildirimi burada: rapor dosyaları diske yazılıp doğrudan tarayıcıda
    açıldığında, bildirim olmadan tarayıcı kodlamayı yanlış tahmin edip Türkçe
    harfleri bozuyordu.
    """
    sekmeler = "".join(
        f'<a class="sekme{" aktif" if yol == aktif else ""}" href="{yol}">{esc(ad)}</a>'
        for yol, ad in SEKMELER
    )
    return f"""<!doctype html>
<html lang="tr"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(baslik)}</title>
<script>{TEMA_ONYUKLEME}</script>
<style>{TEMA}{ek_css}</style>
</head><body>
<header class="ust"><div class="ust-ic">
  <div class="marka"><img src="{logo}" alt="Piramit Bilgisayar"></div>
  <nav class="sekmeler">{sekmeler}</nav>
  <div style="display:flex;gap:8px;align-items:center">
    <a class="tema-dugme" href="/ekran" target="_blank"
       title="Ekran modu — televizyona yansıtmak için" aria-label="Ekran modu"
       style="text-decoration:none;font-size:12.5px;font-weight:600">Ekran</a>
    <a class="tema-dugme{' aktif-ayar' if aktif == '/ayarlar' else ''}" href="/ayarlar"
       title="Mail ayarları" aria-label="Ayarlar"
       style="text-decoration:none">⚙</a>
    <button class="tema-dugme" id="tema" type="button"
            title="Açık/koyu tema" aria-label="Temayı değiştir">☾</button>
    {'<a class="cikis" href="/logout">Çıkış yap</a>' if cikis else ''}
  </div>
</div></header>
<main class="govde">
{govde}
</main>
<script>{TEMA_JS}</script>
</body></html>
"""


# --------------------------------------------------------------------- bileşenler


def kpi(kartlar: list[tuple[str, str, str]], *, one_cikar: bool = False) -> str:
    """(değer, etiket, not) üçlülerinden KPI satırı.

    `one_cikar`: ilk kart daha büyük yazılır. Bir ekranda tek bir "başrol"
    sayı olması, gözün nereden başlayacağını belirsiz bırakmamayı sağlar.
    """
    parcalar = []
    for i, (deger, etiket, notu) in enumerate(kartlar):
        sinif = "k one" if (one_cikar and i == 0) else "k"
        parcalar.append(
            f'<div class="{sinif}"><div class="e">{esc(etiket)}</div>'
            f'<div class="d">{esc(deger)}</div>'
            + (f'<div class="n">{notu}</div>' if notu else "")
            + "</div>"
        )
    return '<div class="kpi">' + "".join(parcalar) + "</div>"


def delta(
    simdi: float | None,
    onceki: float | None,
    *,
    yuksek_iyi: bool = False,
    bicim=lambda d: f"{d:.0f}",
    donem: str = "geçen hafta",
    esik: float = 0.0,
) -> str:
    """Bir sayının önceki döneme göre değişimi.

    Tek başına "60 olay" okuyana bir şey söylemez; karşılaştırma olmadan
    iyi mi kötü mü bilinemez. Önceki dönemin verisi yoksa bu dürüstçe yazılır,
    sıfırla kıyaslanıp sahte bir "%100 artış" üretilmez.
    """
    if simdi is None or onceki is None:
        return f'<span class="delta notr">{esc(donem.capitalize())} verisi yok, kıyaslanamıyor</span>'

    fark = simdi - onceki
    if abs(fark) <= esik:
        return f'<span class="delta notr">{esc(donem.capitalize())} ile aynı</span>'

    artti = fark > 0
    iyi = artti == yuksek_iyi
    ok = "▲" if artti else "▼"
    soz = "arttı" if artti else "azaldı"
    return (
        f'<span class="delta {"iyi" if iyi else "kotu"}">{ok} {esc(bicim(abs(fark)))} {soz}'
        f" · {esc(donem)} {esc(bicim(onceki))}</span>"
    )


def yurt_rozetleri(adlar: list[str], durum: str = "kritik") -> str:
    """Kısa yurt listesi. Sayının arkasındaki 'kimler' sorusunu cevaplar."""
    if not adlar:
        return ""
    renk = {
        "kritik": "var(--kritik)", "uyari": "var(--uyari)",
        "iyi": "var(--iyi)", "notr": "var(--muted)",
    }.get(durum, "var(--muted)")
    return '<div class="rozetler">' + "".join(
        f'<span class="yurt-rozet"><span class="nokta" style="background:{renk}"></span>'
        f"{esc(ad)}</span>"
        for ad in adlar
    ) + "</div>"


def sutun_grafik(
    veriler: list[tuple[str, float]],
    *,
    birim: str = "",
    yukseklik: int = 160,
    bicim=None,
) -> str:
    """Zaman içindeki değişim için sütun grafiği.

    Sütunlar her zaman sıfırdan başlar: kısaltılmış eksen, küçük farkları
    büyük gösterip yanıltır. Kalınlık sınırlıdır — sütun bandı tamamen
    doldurmaz, kalan boşluk grafiği nefes aldırır.
    """
    if not veriler:
        return '<p class="bos">Veri yok.</p>'

    # Ham sayı yerine okunabilir bir birim yazdırmak için (176 -> "2 sa 56 dk").
    yaz = bicim or _sayi

    en_buyuk = max((d for _, d in veriler), default=0) or 1
    n = len(veriler)
    # Sütun sayısı arttıkça bant daralır; aksi halde bir aylık grafik
    # ekrana sığmaz ve etiketler üst üste biner.
    bant = 62 if n <= 8 else (42 if n <= 16 else 28)
    sol, ust, alt = 8, 26, 38
    kalinlik = min(24, bant - 12)
    genislik = max(sol * 2 + n * bant, 260)
    taban = ust + yukseklik

    # Kalabalık grafikte her sütuna değer yazmak okunmaz bir gürültü olur:
    # yalnızca en yüksek sütun etiketlenir, gerisini ipucu balonu taşır.
    hepsini_etiketle = n <= 10
    en_buyuk_indeks = max(range(n), key=lambda i: veriler[i][1])
    # Aynı gerekçeyle gün etiketleri de seyreltilir.
    etiket_adimi = 1 if n <= 10 else (2 if n <= 16 else 5)

    parcalar = []
    for i, (etiket, deger) in enumerate(veriler):
        merkez = sol + i * bant + bant / 2
        x = merkez - kalinlik / 2
        h = (deger / en_buyuk) * yukseklik if deger > 0 else 0
        r = min(4.0, h / 2) if h > 0 else 0

        if deger > 0:
            y = taban - h
            # Üst iki köşe yuvarlak, tabanda köşeli: veri ucu yumuşak,
            # sıfır çizgisi keskin kalsın.
            parcalar.append(
                f'<path d="M{x:.1f},{taban} L{x:.1f},{y + r:.1f} '
                f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                f"L{x + kalinlik - r:.1f},{y:.1f} "
                f"Q{x + kalinlik:.1f},{y:.1f} {x + kalinlik:.1f},{y + r:.1f} "
                f'L{x + kalinlik:.1f},{taban} Z" fill="var(--seri)">'
                f"<title>{esc(etiket)}: {esc(yaz(deger))}{esc(birim)}</title></path>"
            )
            if hepsini_etiketle or i == en_buyuk_indeks:
                parcalar.append(
                    f'<text x="{merkez:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
                    f'font-size="11.5" fill="var(--ink)" font-weight="640">'
                    f"{esc(yaz(deger))}</text>"
                )
        else:
            # Sıfır günler görünmez kalmasın: ince bir iz "ölçüldü, sorun yok" der.
            parcalar.append(
                f'<rect x="{x:.1f}" y="{taban - 2:.1f}" width="{kalinlik}" height="2" '
                f'fill="var(--grid)"><title>{esc(etiket)}: kesinti yok</title></rect>'
            )

        if i % etiket_adimi == 0 or i == n - 1:
            parcalar.append(
                f'<text x="{merkez:.1f}" y="{taban + 19:.1f}" text-anchor="middle" '
                f'font-size="11.5" fill="var(--muted)">{esc(etiket)}</text>'
            )

    return (
        f'<div class="grafik"><svg viewBox="0 0 {genislik} {taban + alt}" width="{genislik}" '
        f'role="img" aria-label="Günlük değerler">'
        f'<line x1="{sol}" y1="{taban}" x2="{genislik - sol}" y2="{taban}" '
        f'stroke="var(--axis)" stroke-width="1"/>' + "".join(parcalar) + "</svg></div>"
    )


def yatay_grafik(
    veriler: list[tuple[str, float]], *, birim: str = "", onek: str = ""
) -> str:
    """Kategorilere göre büyüklük karşılaştırması.

    Uzun Türkçe kategori adları yatayda okunaklı kaldığı için tercih edilir.
    """
    if not veriler:
        return '<p class="bos">Kayıt yok.</p>'
    en_buyuk = max((d for _, d in veriler), default=0) or 1
    satirlar = []
    for etiket, deger in veriler:
        oran = max(2.0, deger / en_buyuk * 100)
        satirlar.append(
            f"""<tr>
  <td style="width:42%">{esc(etiket)}</td>
  <td><div class="olcu"><div class="yol"><div class="dolu" style="width:{oran:.1f}%"></div></div></div></td>
  <td class="sayi" style="width:78px;text-align:right;font-weight:600">{esc(onek)}{esc(_sayi(deger))}{esc(birim)}</td>
</tr>"""
        )
    return f'<div class="sar"><table>{"".join(satirlar)}</table></div>'


def egilim_grafik(
    veriler: list[tuple[str, float | None]],
    *,
    birim: str = "",
    yukseklik: int = 120,
    bicim=None,
) -> str:
    """Haftalık eğilim. Değeri None olan dönemler "ölçülmedi" olarak gösterilir.

    Bir haftayı sıfır çizmek "o hafta hiç sorun olmadı" demek olurdu; oysa
    kastedilen "o hafta izleme çalışmıyordu". İkisi çok farklı şeyler.
    """
    if not veriler:
        return '<p class="bos">Veri yok.</p>'

    olcum = [d for _, d in veriler if d is not None]
    if not olcum:
        return (
            '<p class="bos">Eğilim grafiği için henüz yeterli geçmiş yok. '
            "Haftalar geçtikçe bu grafik kendiliğinden dolacak.</p>"
        )

    yaz = bicim or _sayi
    en_buyuk = max(olcum) or 1
    n = len(veriler)
    bant, sol, ust, alt = 58, 8, 26, 40
    kalinlik = min(22, bant - 14)
    genislik = max(sol * 2 + n * bant, 260)
    taban = ust + yukseklik

    parcalar = []
    for i, (etiket, deger) in enumerate(veriler):
        merkez = sol + i * bant + bant / 2
        x = merkez - kalinlik / 2
        if deger is None:
            # Kesik çizgili boş kutu: "bu dönem ölçülmedi"
            parcalar.append(
                f'<rect x="{x:.1f}" y="{taban - 18:.1f}" width="{kalinlik}" height="18" rx="3" '
                f'fill="none" stroke="var(--grid)" stroke-width="1" stroke-dasharray="3 3">'
                f"<title>{esc(etiket)}: ölçüm yok</title></rect>"
            )
        else:
            h = (deger / en_buyuk) * yukseklik if deger > 0 else 0
            r = min(4.0, h / 2) if h > 0 else 0
            if h > 0:
                y = taban - h
                parcalar.append(
                    f'<path d="M{x:.1f},{taban} L{x:.1f},{y + r:.1f} '
                    f"Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                    f"L{x + kalinlik - r:.1f},{y:.1f} "
                    f"Q{x + kalinlik:.1f},{y:.1f} {x + kalinlik:.1f},{y + r:.1f} "
                    f'L{x + kalinlik:.1f},{taban} Z" fill="var(--seri)">'
                    f"<title>{esc(etiket)}: {esc(yaz(deger))}{esc(birim)}</title></path>"
                )
                parcalar.append(
                    f'<text x="{merkez:.1f}" y="{y - 8:.1f}" text-anchor="middle" '
                    f'font-size="11.5" fill="var(--ink)" font-weight="640">'
                    f"{esc(yaz(deger))}</text>"
                )
            else:
                parcalar.append(
                    f'<rect x="{x:.1f}" y="{taban - 2:.1f}" width="{kalinlik}" height="2" '
                    f'fill="var(--grid)"><title>{esc(etiket)}: 0</title></rect>'
                )
        parcalar.append(
            f'<text x="{merkez:.1f}" y="{taban + 19:.1f}" text-anchor="middle" '
            f'font-size="11" fill="var(--muted)">{esc(etiket)}</text>'
        )

    return (
        f'<div class="grafik"><svg viewBox="0 0 {genislik} {taban + alt}" width="{genislik}" '
        f'role="img" aria-label="Haftalık eğilim">'
        f'<line x1="{sol}" y1="{taban}" x2="{genislik - sol}" y2="{taban}" '
        f'stroke="var(--axis)" stroke-width="1"/>' + "".join(parcalar) + "</svg></div>"
        '<p class="ipucu">Kesik çizgili kutular, o dönemde henüz ölçüm yapılmadığını gösterir.</p>'
    )


def pasta_grafik(dilimler: list[tuple[str, int, str]], *, baslik_ic: str = "") -> str:
    """Halka (donut) grafiği — bütünün parçalara dağılımı.

    Renk tek başına anlam taşımaz: her dilim yanındaki listede adı, adedi ve
    yüzdesiyle birlikte yazılır. Dilimler arasına yüzey rengiyle ince boşluk
    bırakılır; komşu dilimler çizgiyle değil boşlukla ayrılır.
    """
    toplam = sum(d for _, d, _ in dilimler)
    if toplam <= 0:
        return '<p class="bos">Gösterilecek veri yok.</p>'

    boyut, r, ic = 220, 96, 60
    merkez = boyut / 2
    dolu = [(ad, deger, renk) for ad, deger, renk in dilimler if deger > 0]

    parcalar = []
    if len(dolu) == 1:
        # Tek kategori: yay çizimi bozulur (başlangıç ve bitiş aynı noktaya
        # denk gelir), bu yüzden iki daireyle halka çizilir.
        ad, deger, renk = dolu[0]
        parcalar.append(
            f'<circle cx="{merkez}" cy="{merkez}" r="{(r + ic) / 2:.1f}" fill="none" '
            f'stroke="{renk}" stroke-width="{r - ic}">'
            f"<title>{esc(ad)}: {deger} ({deger / toplam * 100:.0f}%)</title></circle>"
        )
    else:
        aci = -90.0  # tepeden başla
        bosluk = 1.4  # derece cinsinden yüzey boşluğu
        for ad, deger, renk in dolu:
            genislik = deger / toplam * 360
            bas, bit = aci + bosluk / 2, aci + genislik - bosluk / 2
            if bit > bas:
                parcalar.append(_halka_dilimi(merkez, r, ic, bas, bit, renk, ad, deger, toplam))
            aci += genislik

    orta = (
        f'<text x="{merkez}" y="{merkez - 4}" text-anchor="middle" font-size="30" '
        f'font-weight="680" fill="var(--ink)">{toplam}</text>'
        f'<text x="{merkez}" y="{merkez + 16}" text-anchor="middle" font-size="11.5" '
        f'fill="var(--muted)">{esc(baslik_ic)}</text>'
    )

    liste = "".join(
        f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:11px">'
        f'<span style="width:11px;height:11px;border-radius:3px;background:{renk};flex:none"></span>'
        f'<span style="font-size:13.5px">{esc(ad)}</span>'
        f'<span style="margin-left:auto;font-size:13.5px;font-weight:650;'
        f'font-variant-numeric:tabular-nums">{deger}</span>'
        f'<span style="font-size:12px;color:var(--muted);width:44px;text-align:right;'
        f'font-variant-numeric:tabular-nums">%{deger / toplam * 100:.0f}</span></div>'
        for ad, deger, renk in dilimler
    )

    return (
        '<div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap">'
        f'<svg viewBox="0 0 {boyut} {boyut}" width="{boyut}" height="{boyut}" '
        f'role="img" aria-label="Dağılım">{"".join(parcalar)}{orta}</svg>'
        f'<div style="flex:1;min-width:190px">{liste}</div>'
        "</div>"
    )


def _halka_dilimi(
    merkez: float, r: float, ic: float, bas: float, bit: float,
    renk: str, ad: str, deger: int, toplam: int,
) -> str:
    import math

    def nokta(yaricap: float, derece: float) -> tuple[float, float]:
        rad = math.radians(derece)
        return merkez + yaricap * math.cos(rad), merkez + yaricap * math.sin(rad)

    x1, y1 = nokta(r, bas)
    x2, y2 = nokta(r, bit)
    x3, y3 = nokta(ic, bit)
    x4, y4 = nokta(ic, bas)
    buyuk = 1 if (bit - bas) > 180 else 0
    return (
        f'<path d="M{x1:.2f},{y1:.2f} A{r},{r} 0 {buyuk} 1 {x2:.2f},{y2:.2f} '
        f"L{x3:.2f},{y3:.2f} A{ic},{ic} 0 {buyuk} 0 {x4:.2f},{y4:.2f} Z\" "
        f'fill="{renk}"><title>{esc(ad)}: {deger} ({deger / toplam * 100:.0f}%)</title></path>'
    )


def rozet(durum: str, yazi: str) -> str:
    renkler = {
        "iyi": ("var(--iyi-ink)", "rgba(12,163,12,.13)"),
        "uyari": ("var(--uyari-ink)", "rgba(250,178,25,.18)"),
        "ciddi": ("var(--ciddi)", "rgba(236,131,90,.16)"),
        "kritik": ("var(--kritik-ink)", "rgba(208,59,59,.13)"),
        "notr": ("var(--muted)", "rgba(137,135,129,.14)"),
    }
    ink, zemin = renkler.get(durum, renkler["notr"])
    return f'<span class="rozet" style="color:{ink};background:{zemin}">{esc(yazi)}</span>'


def kart(baslik: str, icerik: str, aciklama: str = "") -> str:
    """Açıklama satırı, grafiğin ne anlattığını okuyucuya söyler.

    Yönetici raporunda bu şart: "günlük kesinti süresi" başlığı tek başına
    neyin toplandığını anlatmıyor, yanlış yorumlanmaya açık kalıyor.
    """
    ac = f'<p class="kart-ac">{esc(aciklama)}</p>' if aciklama else ""
    return (
        f'<section class="kart"><div class="kart-bas"><h2>{esc(baslik)}</h2>{ac}</div>'
        f"{icerik}</section>"
    )


def _sayi(d: float) -> str:
    if d == int(d):
        return str(int(d))
    return f"{d:.1f}"
