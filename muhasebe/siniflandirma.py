"""Urun siniflandirma: marka, kategori, tur (lisans/abonelik/urun) ve gelir tipi.

Oncelik sirasi her alan icin ayni ve kullanicidan baslar:
    1. Kullanicinin kurallari (Ayarlar > Siniflandirma) — her zaman kazanir
    2. Logo'daki kart bilgisi (MARK tablosu, STGRPCODE)
    3. Yerlesik sozluk (asagida)
    4. Tahmin (yalnizca marka icin: urun adinin ilk kelimesi, en az birkac
       urunde tekrar ediyorsa)
Her degerin kaynagi (`*_src`) saklanir; arayuz tahmin edilenleri ayri
gosterir, kullanici gorup tek tikla kurala cevirebilir.

Lisans/abonelik tespitindeki beyaz liste ilkesi korunuyor: urun adinda
"3YIL" gecmesi lisans oldugu anlamina gelmez ("DELL LATI ... 3YIL" bir
dizustunun garanti suresi). Sureli lisans sayilmasi icin marka beyaz
listede olmali.
"""

import re

# ------------------------------------------------------------------ lisans/abonelik (eski logo_sync.py)
LISANS_MARKALARI = [
    'WATCHGUARD', 'WATCGUARD', 'WATCGHUARD',
    'FORTIGATE', 'FOTIGATE', 'FORTINET',
    'SOPHOS', 'ESET', 'KASPERSKY', 'BITDEFENDER', 'TRELLIX',
    'COMODO', 'XCITIUM', 'SAFETICA',
    'VEEAM', 'VMWARE',
    'PLOG', '5651', 'SIGNLOGGER', 'CRYPTTECH',
    'ADOBE', 'AUTOCAD', 'AUTODESK', 'GEOTRUST',
]
ABONELIK_MARKALARI = ['MICROSOFT', 'AZURE', 'CSP']
KALICI_LISANS_KELIMELERI = ['OEM', 'ESD', 'PERP', 'PERPETUAL', 'GGWA', 'FQC-', 'RETAIL', 'ROK']
DONANIM_KELIMELERI = [
    'APPLIANCEONLY', 'APPLIENCEONLY', 'APLLIANCEONLY', 'APPLIENCEONL',
    'APPLIANCEONL', 'POEAPPLIANCE', 'HARDWARETOKEN',
    'TRANSCEIVER', 'SFP', 'SWITCH', 'ACCESSPOINT', 'POWERINJEKTOR',
    'INJEKTOR', 'INJECTOR', 'RACKMOUNT', 'RACKTRAY', 'MODUL', 'MODULE',
    'CIHAZ', 'KLAVYE', 'MONITOR', 'MONITÖR', 'TABLET', 'KABLO', 'PATCHPANEL',
]


def sure_ay_bul(urun_adi):
    """Urun adindan lisans suresini ay cinsinden cikarir; bulunamazsa None."""
    m = (urun_adi or '').upper()
    yil = re.search(r'(\d+)\s*[-\s]*(?:YIL|YEAR|TEAR)', m)
    if yil:
        return int(yil.group(1)) * 12
    yr = re.search(r'(\d+)\s*[-\s]*YR(?![A-Z0-9])', m)
    if yr:
        return int(yr.group(1)) * 12
    ay = re.search(r'(\d+)\s*(?:AY|MONTH)', m)
    if ay:
        return int(ay.group(1))
    tireli = re.search(r'(?<!\d)(\d)\s*-\s*Y(?![A-Z0-9])', m)
    if tireli:
        return int(tireli.group(1)) * 12
    # "3Y": ardindan harf/rakam gelmemeli ki WGT1850203, SU1YP-00 eslesmesin
    kisa = re.search(r'(?<!\d)(\d)Y(?![A-Z0-9])', m)
    if kisa:
        return int(kisa.group(1)) * 12
    return None


def donanim_mi(urun_adi):
    m = re.sub(r'[^A-Z0-9]', '', (urun_adi or '').upper())
    return any(k in m for k in DONANIM_KELIMELERI)


def kalici_lisans_mi(urun_adi):
    m = (urun_adi or '').upper()
    return any(k in m for k in KALICI_LISANS_KELIMELERI)


def _icerir(m, kelimeler):
    return any(k in m for k in kelimeler)


def tur_bul(urun_adi):
    """'lisans' | 'abonelik' | 'kalici' | 'urun'"""
    m = (urun_adi or '').upper()
    if _icerir(m, ABONELIK_MARKALARI):
        return 'kalici' if kalici_lisans_mi(m) else 'abonelik'
    if _icerir(m, LISANS_MARKALARI) and not donanim_mi(m):
        return 'kalici' if kalici_lisans_mi(m) else 'lisans'
    return 'urun'


# ------------------------------------------------------------------ marka sozlugu
# anahtar kelime(ler) -> kanonik marka adi. Yazim hatali varyantlar dahil.
MARKA_SOZLUGU = [
    (('DELL',), 'Dell'), (('HPE', 'ARUBA', 'PROLIANT'), 'HPE/Aruba'), (('HP',), 'HP'),
    (('LENOVO', 'THINKPAD', 'THINKCENTRE', 'THINKBOOK'), 'Lenovo'),
    (('TP-LINK', 'TPLINK', 'OMADA'), 'TP-Link'), (('ZEBRA',), 'Zebra'), (('LOGITECH',), 'Logitech'),
    (('CISCO', 'MERAKI'), 'Cisco'), (('APC',), 'APC'), (('KINGSTON',), 'Kingston'),
    (('SAMSUNG',), 'Samsung'), (('SYNOLOGY',), 'Synology'), (('SEAGATE',), 'Seagate'),
    (('WESTERN DIGITAL', 'WD'), 'Western Digital'),
    (('WATCHGUARD', 'WATCGUARD', 'WATCGHUARD', 'FIREBOX'), 'WatchGuard'),
    (('FORTIGATE', 'FOTIGATE', 'FORTINET', 'FORTIAUTH'), 'Fortinet'),
    (('ESET',), 'ESET'), (('VEEAM',), 'Veeam'), (('MICROSOFT', 'AZURE', 'OFFICE 365', 'WINDOWS'), 'Microsoft'),
    (('PLOG',), 'PLOG'), (('SIGNLOGGER',), 'SignLogger'), (('CRYPTTECH',), 'CryptTech'),
    (('KASPERSKY',), 'Kaspersky'), (('SOPHOS',), 'Sophos'), (('BITDEFENDER',), 'Bitdefender'),
    (('TRELLIX', 'MCAFEE'), 'Trellix'), (('SAFETICA',), 'Safetica'), (('VMWARE',), 'VMware'),
    (('ADOBE',), 'Adobe'), (('AUTOCAD', 'AUTODESK'), 'Autodesk'), (('GEOTRUST',), 'GeoTrust'),
    (('UBIQUITI', 'UNIFI'), 'Ubiquiti'), (('MIKROTIK',), 'MikroTik'), (('EPSON',), 'Epson'),
    (('CANON',), 'Canon'), (('BROTHER',), 'Brother'), (('XEROX',), 'Xerox'), (('KYOCERA',), 'Kyocera'),
    (('ASUS',), 'Asus'), (('ACER',), 'Acer'), (('MSI',), 'MSI'), (('INTEL',), 'Intel'),
    (('SANDISK',), 'SanDisk'), (('TOSHIBA',), 'Toshiba'), (('HIKVISION',), 'Hikvision'),
    (('DAHUA',), 'Dahua'), (('PHILIPS',), 'Philips'), (('VIEWSONIC',), 'ViewSonic'), (('BENQ',), 'BenQ'),
    (('AOC',), 'AOC'), (('JABRA',), 'Jabra'), (('YEALINK',), 'Yealink'), (('HUAWEI',), 'Huawei'),
    (('NETGEAR',), 'Netgear'), (('D-LINK', 'DLINK'), 'D-Link'), (('ZYXEL',), 'Zyxel'), (('QNAP',), 'QNAP'),
    (('EATON',), 'Eaton'), (('HONEYWELL',), 'Honeywell'), (('DATALOGIC',), 'Datalogic'),
]

KATEGORI_SOZLUGU = [
    ('Dizüstü Bilgisayar', ('LATITUDE', 'THINKPAD', 'PROBOOK', 'ELITEBOOK', 'VIVOBOOK', 'EXPERTBOOK',
                            'IDEAPAD', 'VOSTRO', 'INSPIRON', 'NOTEBOOK', 'LAPTOP', 'MACBOOK', 'ZENBOOK',
                            'THINKBOOK', 'DIZUSTU')),
    ('Masaüstü Bilgisayar', ('OPTIPLEX', 'THINKCENTRE', 'PRODESK', 'ELITEDESK', 'MASAUSTU', 'DESKTOP',
                             'ALL IN ONE', 'MINI PC')),
    ('Sunucu', ('POWEREDGE', 'PROLIANT', 'THINKSYSTEM', 'SUNUCU')),
    ('Monitör', ('MONITOR', 'MONITÖR')),
    ('Projeksiyon', ('PROJEKSIYON', 'PROJEKTOR')),
    ('Yazıcı', ('LASERJET', 'YAZICI', 'PRINTER', 'OFFICEJET', 'ECOTANK', 'MFP')),
    ('Sarf Malzeme', ('TONER', 'KARTUS', 'ETIKET', 'RIBON', 'DRUM', 'MUREKKEP')),
    ('Barkod / Terminal', ('BARKOD', 'BARCODE', 'EL TERMINALI')),
    ('Ağ Ürünleri', ('SWITCH', 'ROUTER', 'ACCESS POINT', 'ARCHER', 'DECO', 'UNIFI', 'MODEM', 'FIREBOX')),
    ('Depolama', ('SSD', 'HDD', 'NVME', 'NAS', 'IRONWOLF', 'EXOS', 'FLASH', 'HARDDISK')),
    ('Bellek', ('DDR4', 'DDR5', 'DIMM', 'SODIMM', ' RAM')),
    ('UPS / Güç', ('UPS', 'AKU', 'PRIZ')),
    ('Kablo / Bağlantı', ('KABLO', 'CABLE', 'PATCH', 'KONNEKTOR', 'RJ45')),
    ('Aksesuar', ('MOUSE', 'KLAVYE', 'KEYBOARD', 'WEBCAM', 'KULAKLIK', 'DOCK', 'CANTA', 'MOUSEPAD',
                  'KABIN', 'ADAPTOR')),
    ('Tablet / Telefon', ('TABLET', 'IPAD', 'TELEFON')),
]

TUR_KATEGORISI = {'lisans': 'Lisans', 'abonelik': 'Bulut Abonelik', 'kalici': 'Yazılım'}

# Logo'daki grup kodlari (STGRPCODE) firmadan firmaya degisir; yaygin olanlar
# sozlukteki kategori adlarina esitlenir ki ayni sey iki ayri kategori gibi
# gorunmesin ("LAPTOP" ve "Dizüstü Bilgisayar"). Eslesmeyen kod oldugu gibi
# kullanilir — kullanicinin kendi gruplamasina saygi.
GRUP_KODU_ESLEME = {
    'LAPTOP': 'Dizüstü Bilgisayar', 'NOTEBOOK': 'Dizüstü Bilgisayar', 'DIZUSTU': 'Dizüstü Bilgisayar',
    'MASAUSTU': 'Masaüstü Bilgisayar', 'DESKTOP': 'Masaüstü Bilgisayar', 'PC': 'Masaüstü Bilgisayar',
    'SUNUCU': 'Sunucu', 'SERVER': 'Sunucu', 'MONITOR': 'Monitör', 'YAZICI': 'Yazıcı', 'PRINTER': 'Yazıcı',
    'SARF': 'Sarf Malzeme', 'TONER': 'Sarf Malzeme', 'BARKOD': 'Barkod / Terminal',
    'AG': 'Ağ Ürünleri', 'NETWORK': 'Ağ Ürünleri', 'DEPOLAMA': 'Depolama', 'STORAGE': 'Depolama',
    'BELLEK': 'Bellek', 'RAM': 'Bellek', 'UPS': 'UPS / Güç', 'KABLO': 'Kablo / Bağlantı',
    'AKSESUAR': 'Aksesuar', 'LISANS': 'Lisans', 'LICENSE': 'Lisans', 'YAZILIM': 'Yazılım',
    'SOFTWARE': 'Yazılım', 'ABONELIK': 'Bulut Abonelik', 'PROJEKSIYON': 'Projeksiyon',
}


def _tr_baslik(metin):
    """Python'un title()'i Turkce I/i'yi bozar: 'ISTANBUL'.title() -> 'Istanbul' dogru ama
    'IZMIR' de 'Izmir' olur; kategori icin yeterli, sadece ilk harf buyuk."""
    return metin[:1].upper() + metin[1:].lower() if metin else metin


def _kelime_var(m, kelime):
    return re.search(rf'(?<![A-Z0-9]){re.escape(kelime)}(?![A-Z0-9])', m) is not None


def kural_uygula(kurallar, alan, ad, kod):
    """Kullanici kurali: urun adinda ya da kodunda gecen metin (buyuk/kucuk harf duyarsiz)."""
    m, k = (ad or '').upper(), (kod or '').upper()
    for kural in kurallar:
        if kural['field'] != alan:
            continue
        p = (kural['pattern'] or '').upper().strip()
        if p and (p in m or p in k):
            return kural['value']
    return None


# Urun adinin ilk kelimesi marka sanilmasin diye: genel urun/hizmet kelimeleri
GENEL_KELIMELER = {
    'HDMI', 'USB', 'USB-C', 'GUC', 'GÜÇ', 'DISPLAYPORT', 'RACK', 'PRIZ', 'MOUSEPAD', 'KABLO', 'ETIKET',
    'RIBON', 'ADAPTOR', 'ADAPTÖR', 'SARJ', 'ŞARJ', 'PATCH', 'KONNEKTOR', 'TONER', 'KARTUS', 'HARICI',
    'DAHILI', 'KASA', 'KLAVYE', 'MOUSE', 'SET', 'PAKET', 'HIZMET', 'HİZMET', 'KURULUM', 'SERVIS', 'BAKIM',
    'DESTEK', 'YAZILIM', 'LISANS', 'KAMERA', 'MONITOR', 'UZATMA', 'CANTA', 'ÇANTA', 'KULAKLIK', 'TAMIR',
    'NAKLIYE', 'KARGO', 'ISCILIK', 'MONTAJ', 'YEDEK', 'PARCA', 'GENEL', 'DIGER', 'ÇEŞİTLİ', 'CESITLI',
}


def ilk_kelime(ad):
    w = (ad or '').strip().split()
    if not w:
        return None
    ham = w[0].upper().lstrip('*')
    if re.search(r'\d', ham):          # CAT6, RJ45, 16GB -> marka degil
        return None
    k = re.sub(r'[^A-ZÇĞİÖŞÜ\-]', '', ham)
    return k if len(k) >= 2 and k not in GENEL_KELIMELER else None


def marka_kanonik(metin):
    """Logo marka karti 'Tp-Link', 'WATCHGUARD' gibi farkli yazimlarla gelebilir."""
    m = (metin or '').upper().strip()
    for kelimeler, ad_ in MARKA_SOZLUGU:
        if m in kelimeler or m == ad_.upper():
            return ad_
    return (metin or '').strip()


def siniflandir(urun, kurallar, ilk_kelime_sayisi):
    """urun: {'name','code','logo_brand','logo_group'} -> eklenmis alanlarla dict."""
    ad, kod = urun.get('name') or '', urun.get('code') or ''
    m = ad.upper()
    tur = tur_bul(ad)
    sure = sure_ay_bul(ad) if tur == 'lisans' else None

    # ---- marka
    marka = kural_uygula(kurallar, 'brand', ad, kod)
    marka_src = 'kural' if marka else None
    if not marka and (urun.get('logo_brand') or '').strip():
        marka, marka_src = marka_kanonik(urun['logo_brand']), 'logo'
    if not marka:
        for kelimeler, ad_ in MARKA_SOZLUGU:
            if any(_kelime_var(m, k) for k in kelimeler):
                marka, marka_src = ad_, 'sozluk'
                break
    if not marka:
        ik = ilk_kelime(ad)
        if ik and ilk_kelime_sayisi.get(ik, 0) >= 3:
            marka, marka_src = ik.title(), 'tahmin'
    if not marka:
        marka, marka_src = 'Markasız', 'yok'

    # ---- kategori
    kat = kural_uygula(kurallar, 'category', ad, kod)
    kat_src = 'kural' if kat else None
    grup = (urun.get('logo_group') or '').strip()
    if not kat and grup:
        anahtar = re.sub(r'[^A-Z]', '', grup.upper().replace('İ', 'I').replace('Ü', 'U').replace('Ö', 'O')
                         .replace('Ş', 'S').replace('Ç', 'C').replace('Ğ', 'G'))
        kat, kat_src = GRUP_KODU_ESLEME.get(anahtar) or _tr_baslik(grup), 'logo'
    if not kat and tur in TUR_KATEGORISI:
        kat, kat_src = TUR_KATEGORISI[tur], 'sozluk'
    if not kat:
        for ad_, kelimeler in KATEGORI_SOZLUGU:
            if any(k.strip() in m and (k[0] != ' ' or k in f' {m}') for k in kelimeler):
                kat, kat_src = ad_, 'sozluk'
                break
    if not kat:
        kat, kat_src = 'Diğer', 'yok'

    # ---- gelir tipi
    gelir = kural_uygula(kurallar, 'revenue_type', ad, kod)
    if not gelir:
        gelir = 'Tekrarlayan' if tur in ('lisans', 'abonelik') else 'Ürün'

    return {**urun, 'brand': marka, 'brand_src': marka_src, 'category': kat, 'category_src': kat_src,
            'kind': tur, 'revenue_type': gelir, 'duration_months': sure}
