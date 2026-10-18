"""Logo ERP'nin birebir taklidi olan demo veritabani ureticisi.

Gercek Logo'ya erisim olmadan (sirket agi disinda) gelistirme ve test
yapabilmek icin. Tablo ve kolon adlari Logo'nun kendisiyle ayni
(LG_001_01_INVOICE, LG_001_01_STLINE, LG_001_ITEMS, LG_001_CLCARD,
LG_SLSMAN, LG_001_MARK), boylece logo_source.py'deki SQL sorgulari hem
gercek MS SQL'de hem bu SQLite dosyasinda AYNEN calisir — test edilen kod
sahadaki kodun kendisi olur.

Gercek veride gozlemlenen tuhafliklar bilerek taklit ediliyor:
  - lisans adlarinda sure "1YIL", "3 YILLIK", "1Y", "12 AY" gibi farkli
    yazimlarla geciyor, bazilarinda hic yok (NEEDS_DURATION testi icin)
  - marka adinda yazim hatalari ("WATCGUARD")
  - urunlerin bir kisminda MARKREF/STGRPCODE bos (siniflandirma kurallari
    testi icin)
  - LINETYPE 0 disi satirlar (indirim, sabit kiymet satisi) — filtrelenmeli
  - iptal edilmis faturalar, iadeler
  - Microsoft aboneliginin bazi aylari musterinin yan firmasina kesiliyor
    (gercekte "riskli abonelik" yanlis alarmina sebep olan durum)

Kullanim:
    python dev/demo_logo.py                 # dev/demo_logo.db, 2016-bugun
    python dev/demo_logo.py --baslangic 2018-01-01 --olcek 2
"""

import argparse
import math
import os
import random
import sqlite3
from datetime import date, datetime, timedelta

FIRMA, DONEM = '001', '01'

# ------------------------------------------------------------------ kur
# USD/TRY icin kaba ama gercekci egri (yil basi -> yil sonu)
KUR_NOKTALARI = [
    (date(2016, 1, 1), 2.92), (date(2017, 1, 1), 3.52), (date(2018, 1, 1), 3.78),
    (date(2018, 8, 15), 6.40), (date(2019, 1, 1), 5.29), (date(2020, 1, 1), 5.95),
    (date(2021, 1, 1), 7.43), (date(2021, 12, 20), 13.0), (date(2022, 1, 1), 13.3),
    (date(2023, 1, 1), 18.7), (date(2023, 7, 1), 26.0), (date(2024, 1, 1), 29.5),
    (date(2025, 1, 1), 35.3), (date(2026, 1, 1), 42.9), (date(2027, 1, 1), 50.0),
]


def usd_kur(g):
    for (d1, k1), (d2, k2) in zip(KUR_NOKTALARI, KUR_NOKTALARI[1:]):
        if d1 <= g <= d2:
            t = (g - d1).days / max((d2 - d1).days, 1)
            return round(k1 + (k2 - k1) * t, 4)
    return KUR_NOKTALARI[-1][1]


# ------------------------------------------------------------------ katalog
# (marka, grup_kodu, ad_sablonu, usd_min, usd_max, agirlik, tip)
# tip: 'urun' fiziksel, 'lisans' sureli lisans, 'abonelik' aylik, 'kalici' tek sefer lisans
MARKALAR = ['DELL', 'HP', 'LENOVO', 'TP-LINK', 'ZEBRA', 'LOGITECH', 'CISCO', 'APC',
            'KINGSTON', 'SAMSUNG', 'SYNOLOGY', 'SEAGATE', 'WATCHGUARD', 'FORTINET',
            'ESET', 'VEEAM', 'MICROSOFT', 'PLOG', 'KASPERSKY', 'UBIQUITI', 'EPSON',
            'ASUS', 'GENERIC']

URUN_AILELERI = [
    # Dell: partner, en buyuk hacim
    ('DELL', 'LAPTOP', 'DELL LATITUDE {m} {cpu} {ram}GB {ssd}SSD W11P', 650, 1650, 30, 'urun',
     {'m': ['3450', '3550', '5450', '5550', '7450', '7650'], 'cpu': ['I5-1335U', 'I7-1355U', 'U5-125U', 'U7-155U'],
      'ram': ['8', '16', '32'], 'ssd': ['256', '512', '1TB']}),
    ('DELL', 'MASAUSTU', 'DELL OPTIPLEX {m} {cpu} {ram}GB {ssd}SSD', 520, 1150, 18, 'urun',
     {'m': ['3000 SFF', '7020 MT', '7010 SFF', 'MICRO 7020'], 'cpu': ['I3-12100', 'I5-13500', 'I7-13700'],
      'ram': ['8', '16'], 'ssd': ['256', '512']}),
    ('DELL', 'SUNUCU', 'DELL POWEREDGE {m} {cpu} {ram}GB', 2400, 9500, 3, 'urun',
     {'m': ['T150', 'R250', 'R350', 'R660', 'T360'], 'cpu': ['XEON E-2314', 'XEON E-2378', 'XEON SILVER 4410Y'],
      'ram': ['16', '32', '64']}),
    ('DELL', 'MONITOR', 'DELL {m} {inc} INC MONITOR', 140, 520, 16, 'urun',
     {'m': ['P2425H', 'P2725H', 'SE2425H', 'U2424H', 'E2225HS'], 'inc': ['22', '24', '27']}),
    ('DELL', 'AKSESUAR', 'DELL {m}', 25, 220, 10, 'urun',
     {'m': ['WD19S DOCK', 'KM5221W KLAVYE MOUSE SET', 'MS116 MOUSE', 'WD22TB4 DOCK', 'ES2422 CANTA']}),
    ('HP', 'LAPTOP', 'HP PROBOOK {m} G{g} {cpu} {ram}GB', 620, 1250, 12, 'urun',
     {'m': ['440', '450', '460'], 'g': ['9', '10', '11'], 'cpu': ['I5-1335U', 'I7-1355U'], 'ram': ['8', '16']}),
    ('HP', 'YAZICI', 'HP LASERJET {m}', 180, 620, 6, 'urun',
     {'m': ['PRO M404DN', 'PRO MFP M428FDW', 'M211DW', 'ENTERPRISE M507DN']}),
    ('HP', 'SARF', 'HP {m} TONER', 45, 160, 8, 'urun', {'m': ['CF259A', 'CF259X', 'W1350A', 'CF226A']}),
    ('LENOVO', 'LAPTOP', 'LENOVO THINKPAD {m} {cpu} {ram}GB', 700, 1550, 9, 'urun',
     {'m': ['E14 G5', 'E16 G2', 'T14 G4', 'L14 G4'], 'cpu': ['I5-1335U', 'R5 7530U', 'I7-1355U'], 'ram': ['8', '16']}),
    ('TP-LINK', 'AG', 'TP-LINK {m}', 25, 260, 12, 'urun',
     {'m': ['ARCHER C6', 'TL-SG1016D 16PORT SWITCH', 'EAP225 ACCESS POINT', 'TL-SG3428 28PORT SWITCH',
            'ER605 ROUTER', 'DECO X50']}),
    ('ZEBRA', 'BARKOD', 'ZEBRA {m}', 90, 620, 6, 'urun',
     {'m': ['ZD421 BARKOD YAZICI', 'DS2208 BARKOD OKUYUCU', 'ZT411 ENDUSTRIYEL YAZICI', 'TC21 EL TERMINALI']}),
    ('ZEBRA', 'SARF', 'ZEBRA {m}', 6, 40, 5, 'urun', {'m': ['ETIKET 100X50 RULO', 'RIBON WAX 110X300', 'ETIKET 58X40 RULO']}),
    ('LOGITECH', 'AKSESUAR', 'LOGITECH {m}', 12, 140, 9, 'urun',
     {'m': ['MK270 KLAVYE MOUSE SET', 'M185 MOUSE', 'C920 WEBCAM', 'MX MASTER 3S', 'H390 KULAKLIK']}),
    ('CISCO', 'AG', 'CISCO {m}', 280, 3200, 3, 'urun', {'m': ['CBS250-24T-4G SWITCH', 'C1000-48P SWITCH', 'CBS350-8FP SWITCH']}),
    ('UBIQUITI', 'AG', 'UBIQUITI {m}', 90, 450, 4, 'urun', {'m': ['UNIFI U6 LITE AP', 'UNIFI U6 PRO AP', 'USW-24-POE SWITCH']}),
    ('APC', 'UPS', 'APC {m}', 110, 1300, 5, 'urun', {'m': ['BX1000MI UPS', 'SMT1500IC UPS', 'SRT3000XLI UPS', 'BX750MI UPS']}),
    ('KINGSTON', 'DEPOLAMA', 'KINGSTON {m}', 25, 180, 6, 'urun', {'m': ['NV2 1TB NVME SSD', 'A400 480GB SSD', '16GB DDR4 RAM', 'KC3000 2TB NVME']}),
    ('SAMSUNG', 'DEPOLAMA', 'SAMSUNG {m}', 60, 260, 3, 'urun', {'m': ['990 PRO 1TB NVME', '870 EVO 1TB SSD']}),
    ('SYNOLOGY', 'DEPOLAMA', 'SYNOLOGY {m}', 300, 1600, 2, 'urun', {'m': ['DS224+ NAS', 'DS923+ NAS', 'RS1221+ NAS']}),
    ('SEAGATE', 'DEPOLAMA', 'SEAGATE {m}', 70, 380, 3, 'urun', {'m': ['IRONWOLF 4TB HDD', 'IRONWOLF 8TB HDD', 'EXOS 16TB HDD']}),
    ('EPSON', 'YAZICI', 'EPSON {m}', 150, 700, 2, 'urun', {'m': ['L3250 TANKLI YAZICI', 'EB-X49 PROJEKSIYON', 'WF-C5790 YAZICI']}),
    ('ASUS', 'LAPTOP', 'ASUS {m}', 480, 950, 2, 'urun', {'m': ['VIVOBOOK 15 I5 8GB', 'EXPERTBOOK B1 I5 16GB']}),
    ('GENERIC', 'KABLO', '{m}', 2, 25, 9, 'urun',
     {'m': ['CAT6 PATCH KABLO 1MT', 'CAT6 PATCH KABLO 3MT', 'HDMI KABLO 3MT', 'CAT6 KABLO 305MT MAKARA',
            'USB-C KABLO 1MT', 'GUC KABLOSU 1.5MT', 'DISPLAYPORT KABLO 2MT']}),
    ('GENERIC', 'AKSESUAR', '{m}', 5, 60, 4, 'urun', {'m': ['RACK KABIN 9U', 'MOUSEPAD', 'PRIZ 6LI GRUP', 'RJ45 KONNEKTOR 100LU']}),
    # Sureli lisanslar — adlarda sure yazimi bilerek tutarsiz
    ('WATCHGUARD', 'LISANS', 'WATCHGUARD {sku} {m} BASIC SECURITY {sure}', 260, 2100, 7, 'lisans',
     {'sku': ['WGT45413', 'WGT25341', 'WGM27333', 'WGM39040301', 'WGT85341'], 'm': ['T45', 'T25', 'M270', 'M390', 'T85'],
      'sure': ['1YIL', '3 YIL', '1 YEAR', '3YILLIK', '1Y', 'RENEWAL 1YIL', '']}),
    ('WATCHGUARD', 'LISANS', 'WATCGUARD {sku} EPDR {sure} {k} KULLANICI', 180, 4200, 4, 'lisans',
     {'sku': ['WGEPDR30101', 'WGEPDR30103', 'WGEPDR30501'], 'sure': ['1 YIL', '3YILLIK', '1 YEAR'], 'k': ['1-50', '51-100', '500']}),
    ('FORTINET', 'LISANS', 'FORTIGATE {m} {sure} LISANS BUNDLE', 300, 2600, 3, 'lisans',
     {'m': ['40F', '60F', '80F', '100F'], 'sure': ['1 YIL', '3 YIL', '12 AY']}),
    ('ESET', 'LISANS', 'ESET PROTECT {m} {k} KULLANICI {sure}', 120, 2200, 3, 'lisans',
     {'m': ['ENTRY', 'ADVANCED', 'COMPLETE'], 'k': ['25', '50', '130'], 'sure': ['1 YIL', '2 YIL', '']}),
    ('VEEAM', 'LISANS', 'VEEAM BACKUP {m} {sure}', 400, 3800, 2, 'lisans',
     {'m': ['ESSENTIALS', 'V-FDNVUL-0I-SU1AR-00 USL', 'ENTERPRISE PLUS'], 'sure': ['1Y', '3Y', '']}),
    ('PLOG', 'LISANS', 'PLOG 5651 {m} {sure} LICENSE', 90, 600, 2, 'lisans', {'m': ['1 QT.FRW.', 'HOTSPOT'], 'sure': ['1 YEAR', '3 YEARS']}),
    ('KASPERSKY', 'LISANS', 'KASPERSKY ENDPOINT {m} {sure}', 120, 1500, 1, 'lisans', {'m': ['SELECT', 'ADVANCED'], 'sure': ['1 YIL', '2 YIL']}),
    # Kalici lisans: tekrar satilir ama abonelik degil
    ('MICROSOFT', 'YAZILIM', 'MICROSOFT {m}', 90, 320, 5, 'kalici',
     {'m': ['WINDOWS 11 PRO OEM', 'OFFICE 2021 HOME BUSINESS ESD', 'WINDOWS SERVER 2022 STD OEM']}),
]

ABONELIK_URUNLERI = [
    ('MICROSOFT CFQ7TTC0LDPB:0001 365 BUSINESS STANDART', 12.5),
    ('MICROSOFT CFQ7TTC0LH16:0001 EXCHANGE ONLINE PLAN1', 4.0),
    ('MICROSOFT CFQ7TTC0LF8R:0001 OFFICE 365 E3', 23.0),
    ('MICROSOFT DZH318Z0BPS60001 AZURE PLAN', 85.0),
    ('MICROSOFT CFQ7TTC0LCHC:0002 365 BUSINESS PREMIUM', 22.0),
]

# ------------------------------------------------------------------ cariler
SEHIRLER = (['ISTANBUL'] * 12 + ['ANKARA'] * 3 + ['IZMIR'] * 2 + ['KOCAELI', 'BURSA', 'KAYSERI', 'ANTALYA',
            'KONYA', 'AYDIN', 'SAKARYA', 'GAZIANTEP', 'AFYONKARAHISAR', 'TEKIRDAG'])
ON_EKLER = ['ANADOLU', 'MARMARA', 'ATLAS', 'EGE', 'KUZEY', 'GUNEY', 'YILDIZ', 'ZIRVE', 'DOGA', 'OZDEMIR',
            'AKSOY', 'KARACA', 'TEKIN', 'ERGUN', 'BOZKURT', 'SAHIN', 'AYDIN', 'KILIC', 'ULUSAL', 'GLOBAL',
            'ARMONI', 'NOVA', 'METRO', 'PIONEER', 'DELTA', 'ORION', 'SAFIR', 'LIMAN', 'KARDELEN', 'PAPATYA',
            'BEYAZ', 'MAVI', 'YESIL', 'ALTIN', 'GUMUS', 'CINAR', 'SERHAT', 'BOGAZICI', 'TOROS', 'UFUK']
SEKTORLER = ['GIDA', 'TEKSTIL', 'INSAAT', 'LOJISTIK', 'ENERJI', 'OTOMOTIV', 'MAKINA', 'PLASTIK', 'AMBALAJ',
             'SAGLIK URUNLERI', 'EGITIM', 'KIMYA', 'MOBILYA', 'ELEKTRIK', 'TURIZM', 'MATBAACILIK', 'METAL',
             'TARIM URUNLERI', 'DANISMANLIK', 'YAZILIM']
UNVANLAR = ['SAN.VE TIC.A.S.', 'SAN.TIC.LTD.STI.', 'A.S.', 'TIC.LTD.STI.', 'ANONIM SIRKETI', 'HOLDING A.S.']
KURUMLAR = ['BELEDIYE BASKANLIGI', 'UNIVERSITESI', 'ILKOGRETIM OKULU', 'VAKFI', 'HASTANESI']
TEDARIKCILER = ['TEKNO DAGITIM A.S.', 'BILISIM TOPTAN A.S.', 'VERI DONANIM DAGITIM LTD.STI.',
                'AG SISTEMLERI DAGITIM A.S.', 'YAZILIM LISANS DAGITIM A.S.', 'BULUT HIZMETLERI DAGITIM A.S.',
                'BARKOD COZUMLERI TOPTAN LTD.STI.', 'GUC KAYNAKLARI DAGITIM A.S.']
TEMSILCILER = ['AYSE KARA', 'MEHMET YILMAZ', 'ZEYNEP ARSLAN', 'EMRE CELIK', 'BURAK DEMIR', 'SELIN KOC']


def _yaz_tablolari(c):
    c.executescript(f"""
    CREATE TABLE LG_{FIRMA}_MARK (LOGICALREF INTEGER PRIMARY KEY, CODE TEXT, DESCR TEXT);
    CREATE TABLE LG_{FIRMA}_ITEMS (
        LOGICALREF INTEGER PRIMARY KEY, CODE TEXT, NAME TEXT, CARDTYPE INTEGER,
        STGRPCODE TEXT, SPECODE TEXT, MARKREF INTEGER, PRODUCERCODE TEXT, ACTIVE INTEGER DEFAULT 0);
    CREATE TABLE LG_{FIRMA}_CLCARD (
        LOGICALREF INTEGER PRIMARY KEY, CODE TEXT, DEFINITION_ TEXT, CARDTYPE INTEGER,
        EMAILADDR TEXT, TELNRS1 TEXT, CITY TEXT, SPECODE TEXT, ACTIVE INTEGER DEFAULT 0);
    CREATE TABLE LG_SLSMAN (LOGICALREF INTEGER PRIMARY KEY, CODE TEXT, DEFINITION_ TEXT, FIRMNR INTEGER);
    CREATE TABLE LG_{FIRMA}_{DONEM}_INVOICE (
        LOGICALREF INTEGER PRIMARY KEY, FICHENO TEXT, DATE_ TEXT, TRCODE INTEGER, CLIENTREF INTEGER,
        SALESMANREF INTEGER, GROSSTOTAL REAL, NETTOTAL REAL, TOTALVAT REAL, REPORTRATE REAL,
        TRCURR INTEGER, TRRATE REAL, CANCELLED INTEGER, SPECODE TEXT);
    CREATE TABLE LG_{FIRMA}_{DONEM}_STLINE (
        LOGICALREF INTEGER PRIMARY KEY, STOCKREF INTEGER, LINETYPE INTEGER, TRCODE INTEGER, DATE_ TEXT,
        IOCODE INTEGER, SOURCEINDEX INTEGER, INVOICEREF INTEGER, STFICHEREF INTEGER, CLIENTREF INTEGER,
        SALESMANREF INTEGER, AMOUNT REAL, PRICE REAL, TOTAL REAL, DISTDISC REAL, LINENET REAL,
        VATAMNT REAL, REPORTRATE REAL, TRCURR INTEGER, TRRATE REAL, CANCELLED INTEGER, LINEEXP TEXT);
    CREATE TABLE L_DAILYEXCHANGES (LREF INTEGER PRIMARY KEY, EDATE TEXT, CRTYPE INTEGER, RATES1 REAL);
    CREATE INDEX IX_STL_DATE ON LG_{FIRMA}_{DONEM}_STLINE(DATE_);
    CREATE INDEX IX_STL_INV ON LG_{FIRMA}_{DONEM}_STLINE(INVOICEREF);
    """)


class Uretici:
    def __init__(self, baslangic, bitis, olcek, tohum):
        self.r = random.Random(tohum)
        self.bas, self.bit, self.olcek = baslangic, bitis, olcek
        self.markalar, self.urunler, self.cariler, self.musteriler = {}, [], [], []
        self.tedarikciler, self.temsilciler = [], []
        self.faturalar, self.satirlar = [], []
        self.stok = {}  # urun_ref -> eldeki miktar
        self.inv_ref = self.stl_ref = 0
        self.fis_sayac = {}

    # ---------------------------------------------------------- kartlar
    def kartlari_uret(self):
        r = self.r
        for i, m in enumerate(MARKALAR, 1):
            self.markalar[m] = i
        ref = 0
        for (marka, grup, sablon, umin, umax, agirlik, tip, secenekler) in URUN_AILELERI:
            # Gercek katalogda ayni modelin onlarca konfigurasyonu/parca
            # numarasi var — kombinasyon bitince adin sonuna P/N eklenir.
            adet = max(3, int(agirlik * 14 * self.olcek))
            gorulen = set()
            deneme = 0
            while len(gorulen) < adet and deneme < adet * 20:
                deneme += 1
                ad = sablon.format(**{k: r.choice(v) for k, v in secenekler.items()})
                ad = ' '.join(ad.split())
                if ad in gorulen and tip in ('urun', 'kalici'):
                    harf = ''.join(r.choice('ABCDEFGHJKLMNPRSTVXYZ') for _ in range(2))
                    ad = f"{ad} {harf}{r.randint(100, 999)}{r.choice(['', 'TR', 'EU', '-K'])}"
                if ad in gorulen:
                    continue
                gorulen.add(ad)
                ref += 1
                usd = round(r.uniform(umin, umax), 2)
                # %30 urunde marka karti, %40'inda grup kodu bos (siniflandirma testi)
                markref = self.markalar[marka] if (marka != 'GENERIC' and r.random() > 0.3) else 0
                grup_kodu = grup if r.random() > 0.4 else ''
                self.urunler.append({
                    'ref': ref, 'kod': f'{marka[:3]}{ref:05d}', 'ad': ad, 'marka': marka, 'grup': grup,
                    'grup_kodu': grup_kodu, 'markref': markref, 'tip': tip, 'usd': usd,
                    'agirlik': agirlik / max(adet, 1) * (1 + r.random()),
                })
        for urun_ad, usd in ABONELIK_URUNLERI:
            ref += 1
            self.urunler.append({
                'ref': ref, 'kod': f'MSC{ref:05d}', 'ad': urun_ad, 'marka': 'MICROSOFT', 'grup': 'ABONELIK',
                'grup_kodu': 'ABONELIK', 'markref': self.markalar['MICROSOFT'], 'tip': 'abonelik',
                'usd': usd, 'agirlik': 0,
            })
        self.urun_by_ref = {u['ref']: u for u in self.urunler}

        # Temsilciler
        for i, ad in enumerate(TEMSILCILER, 1):
            self.temsilciler.append({'ref': i, 'kod': f'S{i:03d}', 'ad': ad})

        # Musteriler: guc yasasi dagilimi (az sayida buyuk musteri)
        hedef = int(900 * self.olcek)
        isimler = set()
        ref = 0
        gruplar = []  # yan firma gruplari
        while len(self.musteriler) < hedef:
            if r.random() < 0.08:
                ad = f"{r.choice(ON_EKLER)} {r.choice(SEHIRLER).title().upper()} {r.choice(KURUMLAR)}"
            else:
                ad = f"{r.choice(ON_EKLER)} {r.choice(SEKTORLER)} {r.choice(UNVANLAR)}"
            if ad in isimler:
                continue
            isimler.add(ad)
            ref += 1
            boyut = r.paretovariate(1.6)
            bas_gun = r.randint(0, max(1, (self.bit - self.bas).days - 200))
            aktif_bas = self.bas + timedelta(days=int(bas_gun * r.random()))
            # %25 musteri bir noktada kopuyor
            aktif_bit = self.bit if r.random() > 0.25 else aktif_bas + timedelta(days=r.randint(200, 2500))
            kod_on = ad.split()[0][:3]
            m = {
                'ref': ref, 'kod': f'120{ref:04d}', 'ad': ad, 'tip': 1,
                'mail': (f"muhasebe@{kod_on.lower()}{ref}.com.tr" if r.random() > 0.35 else ''),
                'tel': (f"{r.choice(['212', '216', '312', '232', '262'])}-{r.randint(200, 999)}{r.randint(1000, 9999)}"
                        if r.random() > 0.2 else ''),
                'sehir': r.choice(SEHIRLER), 'boyut': boyut, 'aktif_bas': aktif_bas,
                'aktif_bit': min(aktif_bit, self.bit), 'temsilci': r.choice(self.temsilciler)['ref'],
                'ilgi': r.sample([a[1] for a in URUN_AILELERI], k=r.randint(2, 6)),
                'yan': None,
            }
            self.musteriler.append(m)
        # Yan firmalar: %4 musteriye ayni on ekli bir kardes firma
        for m in r.sample(self.musteriler, k=max(3, len(self.musteriler) // 25)):
            on = m['ad'].split()[0]
            ad = f"{on} {r.choice(['ENERJI', 'HOLDING', 'ENDUSTRI', 'DIS TICARET'])} {r.choice(['A.S.', 'LTD.STI.'])}"
            if ad in isimler:
                continue
            isimler.add(ad)
            ref += 1
            kardes = dict(m, ref=ref, kod=f'120{ref:04d}', ad=ad, boyut=m['boyut'] * 0.3, yan=m['ref'])
            m['yan'] = ref
            self.musteriler.append(kardes)
        for i, ad in enumerate(TEDARIKCILER, 1):
            ref += 1
            self.tedarikciler.append({'ref': ref, 'kod': f'320{i:04d}', 'ad': ad, 'tip': 2,
                                      'mail': f'satis@tedarikci{i}.com.tr', 'tel': '', 'sehir': 'ISTANBUL'})
        self.cariler = self.musteriler + self.tedarikciler
        self.musteri_by_ref = {m['ref']: m for m in self.musteriler}

    # ---------------------------------------------------------- fis yazimi
    def _fis_no(self, on, tarih):
        anahtar = (on, tarih.year)
        self.fis_sayac[anahtar] = self.fis_sayac.get(anahtar, 0) + 1
        return f'{on}{tarih.year}{self.fis_sayac[anahtar]:09d}'

    def fatura(self, tarih, trcode, cari_ref, temsilci_ref, kalemler, iptal=False):
        """kalemler: [(urun_ref, miktar, birim_usd, indirim_orani)]"""
        self.inv_ref += 1
        kur = usd_kur(tarih)
        on = {8: 'PRM', 7: 'PER', 9: 'HZM', 1: 'ALS', 4: 'ALH', 3: 'SIA', 6: 'AIA'}[trcode]
        iocode = {8: 4, 7: 4, 9: 4, 1: 1, 4: 1, 3: 1, 6: 4}[trcode]
        fis = self._fis_no(on, tarih)
        saat = f"{tarih.isoformat()} {self.r.randint(8, 18):02d}:{self.r.randint(0, 59):02d}:00.000"
        brut = net = 0.0
        for urun_ref, miktar, birim_usd, ind in kalemler:
            self.stl_ref += 1
            fiyat_tl = round(birim_usd * kur, 2)
            toplam = round(fiyat_tl * miktar, 2)
            indirim = round(toplam * ind, 2)
            satir_net = round(toplam - indirim, 2)
            brut += toplam
            net += satir_net
            self.satirlar.append((
                self.stl_ref, urun_ref, 0, trcode, saat, iocode, 0, self.inv_ref, 0, cari_ref, temsilci_ref,
                miktar, fiyat_tl, toplam, indirim, satir_net, round(satir_net * 0.20, 2),
                # Gercek Logo'da raporlama kuru bazen bos gelir -> L_DAILYEXCHANGES yedegi
                kur if self.r.random() > 0.08 else 0, 0, 1.0,
                1 if iptal else 0, ''))
            if not iptal:
                self.stok[urun_ref] = self.stok.get(urun_ref, 0) + (miktar if iocode == 1 else -miktar)
        # Gercek veride gorulen gurultu: indirim satiri (LINETYPE 2)
        if not iptal and trcode == 8 and self.r.random() < 0.04:
            self.stl_ref += 1
            self.satirlar.append((self.stl_ref, 0, 2, trcode, saat, 0, 0, self.inv_ref, 0, cari_ref, temsilci_ref,
                                  0, 0, 0, 0, round(-net * 0.02, 2), 0, kur, 0, 1.0, 0, 'GENEL INDIRIM'))
        self.faturalar.append((self.inv_ref, fis, saat, trcode, cari_ref, temsilci_ref, round(brut, 2),
                               round(net, 2), round(net * 0.2, 2), kur, 0, 1.0, 1 if iptal else 0, ''))
        return self.inv_ref

    # ---------------------------------------------------------- simulasyon
    def _gunluk_fatura_beklentisi(self, g):
        yil_orani = (g - self.bas).days / 365.25
        trend = 1.0 + 0.09 * yil_orani                      # yillik buyume
        mevsim = 1.0 + 0.18 * math.sin((g.timetuple().tm_yday / 365.25) * 2 * math.pi - 1.2)
        aralik = 1.35 if g.month == 12 else (0.7 if g.month == 8 else 1.0)  # yil sonu, yaz tatili
        return 7.5 * self.olcek * trend * mevsim * aralik

    def _poisson(self, lam):
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.r.random()
            if p <= l:
                return k
            k += 1

    def _tedarik(self, tarih, kalemler):
        """Satis icin stok yetmiyorsa birkac gun (bazen aylar) once alis yap."""
        r = self.r
        eksik = []
        for urun_ref, miktar, _, _ in kalemler:
            urun = self.urun_by_ref[urun_ref]
            if urun['tip'] == 'abonelik':
                continue
            if self.stok.get(urun_ref, 0) < miktar:
                # Populer urunde toplu alim: depoda bekleyen stok olusur
                ek = r.choice([0, 0, 0, 2, 5, 10]) if urun['tip'] == 'urun' else 0
                eksik.append((urun_ref, miktar - self.stok.get(urun_ref, 0) + ek, urun['usd'] * r.uniform(0.72, 0.88), 0))
        if eksik:
            geri = r.choice([0, 1, 2, 3, 5, 7, 14, 30, 90, 200]) if r.random() < 0.85 else r.randint(200, 500)
            alis_tarihi = max(self.bas, tarih - timedelta(days=geri))
            while alis_tarihi.weekday() >= 5:
                alis_tarihi -= timedelta(days=1)
            ted = r.choice(self.tedarikciler)['ref']
            self.fatura(alis_tarihi, 1, ted, 0, eksik)

    def _kalemler_sec(self, musteri):
        r = self.r
        adaylar = [u for u in self.urunler if u['grup'] in musteri['ilgi'] and u['tip'] in ('urun', 'kalici')]
        if not adaylar or r.random() < 0.15:
            adaylar = [u for u in self.urunler if u['tip'] in ('urun', 'kalici')]
        satir_sayisi = r.choices([1, 2, 3, 4, 5, 6], weights=[40, 25, 15, 10, 6, 4])[0]
        kalemler = []
        for u in r.choices(adaylar, weights=[a['agirlik'] for a in adaylar], k=satir_sayisi):
            if any(k[0] == u['ref'] for k in kalemler):
                continue
            ucuz = u['usd'] < 30
            miktar = r.choice([1, 1, 1, 2, 2, 3, 5, 10, 20]) if not ucuz else r.choice([1, 5, 10, 20, 50])
            if musteri['boyut'] > 5 and not ucuz:
                miktar *= r.choice([1, 2, 5])
            marj = r.uniform(1.08, 1.32)
            ind = r.choice([0, 0, 0, 0.03, 0.05, 0.1])
            kalemler.append((u['ref'], float(miktar), round(u['usd'] * marj, 2), ind))
        return kalemler

    def simule_et(self):
        r = self.r
        g = self.bas
        agirliklar = [m['boyut'] for m in self.musteriler]
        lisans_urunleri = [u for u in self.urunler if u['tip'] == 'lisans']
        planli_lisans = {}  # tarih -> [(musteri_ref, urun_ref, temsilci)]
        abonelikler = []

        # Microsoft abonelikleri: musterilerin ~%8'i
        for m in r.sample(self.musteriler, k=max(4, len(self.musteriler) // 12)):
            urun = r.choice([u for u in self.urunler if u['tip'] == 'abonelik'])
            bas = max(self.bas, m['aktif_bas']) + timedelta(days=r.randint(0, 900))
            if bas >= self.bit:
                continue
            bit = self.bit if r.random() > 0.3 else bas + timedelta(days=r.randint(120, 1500))
            abonelikler.append({'musteri': m, 'urun': urun, 'bas': bas, 'bit': min(bit, self.bit),
                                'adet': r.choice([5, 10, 15, 25, 40, 80]),
                                'aralik': r.choice([30, 30, 30, 31, 33, 41])})

        while g <= self.bit:
            if g.weekday() < 5:
                # --- urun satislari
                for _ in range(self._poisson(self._gunluk_fatura_beklentisi(g))):
                    m = r.choices(self.musteriler, weights=agirliklar)[0]
                    if not (m['aktif_bas'] <= g <= m['aktif_bit']):
                        continue
                    kalemler = self._kalemler_sec(m)
                    if not kalemler:
                        continue
                    self._tedarik(g, kalemler)
                    trcode = 7 if r.random() < 0.01 else 8
                    iptal = r.random() < 0.012
                    self.fatura(g, trcode, m['ref'], m['temsilci'], kalemler, iptal=iptal)
                    # %0.6 iade
                    if not iptal and r.random() < 0.006:
                        ur, mk, fy, _ = kalemler[0]
                        self.fatura(g + timedelta(days=r.randint(2, 20)), 3, m['ref'], m['temsilci'],
                                    [(ur, 1.0, fy, 0)])

                # --- yeni lisans satislari
                for _ in range(self._poisson(0.55 * self.olcek)):
                    m = r.choices(self.musteriler, weights=agirliklar)[0]
                    if not (m['aktif_bas'] <= g <= m['aktif_bit']):
                        continue
                    u = r.choice(lisans_urunleri)
                    self._lisans_sat(g, m, u, planli_lisans)

                # --- planlanmis yenilemeler
                for (mref, uref, tref) in planli_lisans.pop(g, []):
                    m = self.musteri_by_ref[mref]
                    if g > m['aktif_bit']:
                        continue
                    eski = self.urun_by_ref[uref]
                    secim = r.random()
                    if secim < 0.55:
                        yeni = eski                                  # birebir ayni urun
                    elif secim < 0.85:
                        ayni_marka = [u for u in lisans_urunleri if u['marka'] == eski['marka']]
                        yeni = r.choice(ayni_marka)                  # farkli SKU / sure
                    else:
                        continue                                     # yenilemedi -> kayip
                    self._lisans_sat(g, m, yeni, planli_lisans)

                # --- sabit kiymet satisi gurultusu (LINETYPE 8), yilda bir
                if g.month == 6 and g.day == 15:
                    self.inv_ref += 1
                    self.stl_ref += 1
                    saat = f"{g.isoformat()} 10:00:00.000"
                    kur = usd_kur(g)
                    self.satirlar.append((self.stl_ref, 0, 8, 8, saat, 4, 0, self.inv_ref, 0, self.musteriler[0]['ref'],
                                          0, 1, 0, 1_500_000, 0, 1_500_000, 0, kur, 0, 1.0, 0, 'SIRKET ARACI SATISI'))
                    self.faturalar.append((self.inv_ref, self._fis_no('PRM', g), saat, 8, self.musteriler[0]['ref'], 0,
                                           1_500_000, 1_500_000, 0, kur, 0, 1.0, 0, ''))

            # --- abonelik faturalari (her gun kontrol)
            for a in abonelikler:
                if a['bas'] <= g <= a['bit'] and ((g - a['bas']).days % a['aralik'] == 0):
                    m = a['musteri']
                    # %15 ihtimalle o ayin faturasi kardes firmaya kesilir
                    cari = m['yan'] if (m['yan'] and r.random() < 0.15) else m['ref']
                    fiyat = a['urun']['usd'] * r.uniform(1.1, 1.18)
                    kalem = [(a['urun']['ref'], float(a['adet']), round(fiyat, 2), 0)]
                    self.fatura(g, 1, r.choice(self.tedarikciler)['ref'], 0,
                                [(a['urun']['ref'], float(a['adet']), round(a['urun']['usd'], 2), 0)])
                    self.fatura(g, 9, cari, m['temsilci'], kalem)
            g += timedelta(days=1)

    def _lisans_sat(self, g, m, u, planli):
        r = self.r
        adet = 1.0
        kalem = [(u['ref'], adet, round(u['usd'] * r.uniform(1.12, 1.3), 2), 0)]
        self._tedarik(g, kalem)
        self.fatura(g, 8, m['ref'], m['temsilci'], kalem)
        ad = u['ad']
        yil = 3 if ('3' in ad and ('YIL' in ad or 'Y' in ad)) else 1
        yenileme = g + timedelta(days=365 * yil + r.randint(-20, 25))
        while yenileme.weekday() >= 5:
            yenileme += timedelta(days=1)
        if yenileme <= self.bit:
            planli.setdefault(yenileme, []).append((m['ref'], u['ref'], m['temsilci']))

    # ---------------------------------------------------------- disa yazim
    def yaz(self, yol):
        if os.path.exists(yol):
            os.remove(yol)
        c = sqlite3.connect(yol)
        _yaz_tablolari(c)
        c.executemany(f'INSERT INTO LG_{FIRMA}_MARK VALUES (?,?,?)',
                      [(ref, m, m.title() if m not in ('HP', 'APC', 'ESET', 'PLOG') else m)
                       for m, ref in self.markalar.items()])
        c.executemany(f'INSERT INTO LG_{FIRMA}_ITEMS VALUES (?,?,?,?,?,?,?,?,0)',
                      [(u['ref'], u['kod'], u['ad'], 1, u['grup_kodu'], '', u['markref'], '') for u in self.urunler])
        c.executemany(f'INSERT INTO LG_{FIRMA}_CLCARD VALUES (?,?,?,?,?,?,?,?,0)',
                      [(k['ref'], k['kod'], k['ad'], k['tip'], k['mail'], k['tel'], k['sehir'], '')
                       for k in self.cariler])
        c.executemany('INSERT INTO LG_SLSMAN VALUES (?,?,?,1)',
                      [(t['ref'], t['kod'], t['ad']) for t in self.temsilciler])
        c.executemany(f'INSERT INTO LG_{FIRMA}_{DONEM}_INVOICE VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', self.faturalar)
        c.executemany(f'INSERT INTO LG_{FIRMA}_{DONEM}_STLINE VALUES ({",".join("?" * 22)})', self.satirlar)
        kurlar, g, i = [], self.bas, 0
        while g <= self.bit:
            i += 1
            kurlar.append((i, f"{g.isoformat()} 00:00:00.000", 1, usd_kur(g)))
            g += timedelta(days=1)
        c.executemany('INSERT INTO L_DAILYEXCHANGES VALUES (?,?,?,?)', kurlar)
        c.commit()
        c.close()


def main():
    p = argparse.ArgumentParser(description='Logo taklidi demo veritabani uret')
    p.add_argument('--cikti', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'demo_logo.db'))
    p.add_argument('--baslangic', default='2016-01-01')
    p.add_argument('--bitis', default=date.today().isoformat())
    p.add_argument('--olcek', type=float, default=1.0, help='1.0 ~ 120 bin satir')
    p.add_argument('--tohum', type=int, default=42)
    a = p.parse_args()

    t0 = datetime.now()
    u = Uretici(date.fromisoformat(a.baslangic), date.fromisoformat(a.bitis), a.olcek, a.tohum)
    u.kartlari_uret()
    u.simule_et()
    u.yaz(a.cikti)
    sure = (datetime.now() - t0).total_seconds()
    print(f'{a.cikti}\n  {len(u.urunler):,} urun, {len(u.cariler):,} cari, '
          f'{len(u.faturalar):,} fatura, {len(u.satirlar):,} satir  ({sure:.1f} sn)')


if __name__ == '__main__':
    main()
