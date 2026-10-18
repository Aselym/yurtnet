"""Logo veri kaynagi: gercek MS SQL Server ya da demo (SQLite) — ayni SQL.

Ikisi arasindaki tek fark iki kucuk lehce ayrintisi:
  - MS SQL'de her tablo WITH (NOLOCK) ile okunur (Logo'da fatura kesen
    muhasebe ekibi kilitlenmesin diye); SQLite bunu tanimaz.
  - MS SQL'de metin kolonlari CAST(... AS NVARCHAR) ile cekilir ki Turkce
    karakterleri sunucu kendi collation'iyla donustursun (istemci tarafinda
    cp1254 zorlamak bir urun adindaki tek bozuk bayt yuzunden tum senkronu
    cokertiyordu).

Geri kalan her sey ortak; boylece demo veritabaniyla test edilen sorgu,
sahada calisan sorgunun kendisi olur.

Logo'ya asla yazilmaz.
"""

import os
from datetime import date, datetime

DEMO_DB_VARSAYILAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dev', 'demo_logo.db')


def _odbc_surucusu():
    try:
        import pyodbc
        mevcut = pyodbc.drivers()
    except Exception:
        return 'SQL Server'
    for d in ('ODBC Driver 18 for SQL Server', 'ODBC Driver 17 for SQL Server', 'SQL Server'):
        if d in mevcut:
            return d
    return 'SQL Server'


def tarih_str(deger):
    """pyodbc datetime da, SQLite metni de 'YYYY-MM-DD' olur."""
    if deger is None:
        return None
    if isinstance(deger, (datetime, date)):
        return deger.strftime('%Y-%m-%d')
    return str(deger)[:10]


def donemler(ayarlar):
    """'01' ya da '01,02,03' — bazi firmalar her yil yeni donem acar."""
    ham = (ayarlar.get('logo_period_no') or '01').replace(' ', '')
    return [p.zfill(2) for p in ham.split(',') if p]


class LogoKaynagi:
    def __init__(self, ayarlar):
        self.ayarlar = ayarlar
        self.mod = (ayarlar.get('logo_source') or 'mssql').lower()
        self.firma = (ayarlar.get('logo_firm_no') or '001').zfill(3)
        self.donemler = donemler(ayarlar)
        self._conn = None

    # ------------------------------------------------------------ baglanti
    def __enter__(self):
        self.baglan()
        return self

    def __exit__(self, *a):
        self.kapat()

    def baglan(self):
        if self.mod == 'demo':
            import sqlite3
            yol = self.ayarlar.get('demo_db_path') or DEMO_DB_VARSAYILAN
            if not os.path.exists(yol):
                raise FileNotFoundError(
                    f"Demo veritabanı bulunamadı: {yol}. Oluşturmak için: python dev/demo_logo.py")
            self._conn = sqlite3.connect(f'file:{yol}?mode=ro', uri=True)
        else:
            import pyodbc
            a = self.ayarlar
            surucu = _odbc_surucusu()
            ek = 'Encrypt=no;TrustServerCertificate=yes;' if '18' in surucu else ''
            self._conn = pyodbc.connect(
                f"DRIVER={{{surucu}}};SERVER={a.get('logo_sql_server', '127.0.0.1')},"
                f"{a.get('logo_sql_port', '1433')};DATABASE={a.get('logo_sql_db', 'LOGO')};"
                f"UID={a.get('logo_sql_user', '')};PWD={a.get('logo_sql_pass', '')};{ek}Timeout=10;")
        return self._conn

    def kapat(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------ lehce
    @property
    def nl(self):
        return '' if self.mod == 'demo' else ' WITH (NOLOCK)'

    def txt(self, ifade, n=200):
        return ifade if self.mod == 'demo' else f'CAST({ifade} AS NVARCHAR({n}))'

    def t(self, tablo, donem=None):
        """Logo tablo adi: 'ITEMS' -> LG_001_ITEMS, ('STLINE','01') -> LG_001_01_STLINE."""
        return f'LG_{self.firma}_{donem}_{tablo}' if donem else f'LG_{self.firma}_{tablo}'

    # ------------------------------------------------------------ okuma
    def sorgu(self, sql, params=(), parca=5000):
        """Satirlari dict olarak, bellegi sisirmeden parca parca dondurur."""
        cur = self._conn.cursor()
        cur.execute(sql, params)
        kolonlar = [d[0].lower() for d in cur.description]
        while True:
            satirlar = cur.fetchmany(parca)
            if not satirlar:
                break
            for s in satirlar:
                yield dict(zip(kolonlar, s))

    def tek(self, sql, params=()):
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()

    # ------------------------------------------------------------ Logo tablolari
    def markalar(self):
        try:
            return {r['ref']: (r['descr'] or r['code'] or '').strip()
                    for r in self.sorgu(f"SELECT LOGICALREF AS ref, {self.txt('CODE', 50)} AS code, "
                                        f"{self.txt('DESCR', 100)} AS descr FROM {self.t('MARK')}{self.nl}")}
        except Exception:
            # Eski Logo surumlerinde marka karti tablosu olmayabilir
            return {}

    def urunler(self):
        return self.sorgu(f"""
            SELECT LOGICALREF AS ref, {self.txt('CODE', 50)} AS code, {self.txt('NAME', 200)} AS name,
                   CARDTYPE AS cardtype, {self.txt('STGRPCODE', 50)} AS grp, {self.txt('SPECODE', 50)} AS specode,
                   MARKREF AS markref
            FROM {self.t('ITEMS')}{self.nl}""")

    def cariler(self):
        return self.sorgu(f"""
            SELECT LOGICALREF AS ref, {self.txt('CODE', 50)} AS code, {self.txt('DEFINITION_', 200)} AS name,
                   CARDTYPE AS cardtype, {self.txt('EMAILADDR', 200)} AS email, {self.txt('TELNRS1', 50)} AS phone,
                   {self.txt('CITY', 50)} AS city
            FROM {self.t('CLCARD')}{self.nl}""")

    def temsilciler(self):
        return self.sorgu(f"""
            SELECT LOGICALREF AS ref, {self.txt('CODE', 50)} AS code, {self.txt('DEFINITION_', 100)} AS name
            FROM LG_SLSMAN{self.nl}""")

    def doviz_kurlari(self):
        """L_DAILYEXCHANGES: gunluk USD kuru. STLINE.REPORTRATE bos oldugunda kullanilir."""
        try:
            return {tarih_str(r['edate']): float(r['rate'])
                    for r in self.sorgu(f"SELECT EDATE AS edate, RATES1 AS rate FROM L_DAILYEXCHANGES{self.nl} "
                                        f"WHERE CRTYPE = 1 AND RATES1 > 0")}
        except Exception:
            return {}

    def satirlar(self, baslangic=None):
        """Tum stok hareket satirlari (fatura satirlari dahil), donem donem.

        Fatura baslik bilgisi (fis no, iptal) LEFT JOIN ile gelir; irsaliye/
        ambar fisi satirlarinda fatura yoktur ama stok hesabi icin gereklidir.
        """
        for donem in self.donemler:
            kosul, params = '', ()
            if baslangic:
                kosul, params = 'WHERE STL.DATE_ >= ?', (baslangic,)
            yield from self.sorgu(f"""
                SELECT '{donem}' AS period, STL.LOGICALREF AS line_ref, STL.INVOICEREF AS inv_ref, STL.DATE_ AS date,
                       STL.TRCODE AS trcode, STL.IOCODE AS iocode, STL.LINETYPE AS linetype,
                       STL.STOCKREF AS item_ref, STL.CLIENTREF AS client_ref, STL.SALESMANREF AS salesman_ref,
                       STL.AMOUNT AS qty, STL.PRICE AS price, STL.TOTAL AS gross, STL.LINENET AS net,
                       STL.REPORTRATE AS rate, STL.CANCELLED AS line_cancelled,
                       {self.txt('INV.FICHENO', 50)} AS fiche_no, INV.CANCELLED AS inv_cancelled,
                       INV.SALESMANREF AS inv_salesman, INV.CLIENTREF AS inv_client
                FROM {self.t('STLINE', donem)} STL{self.nl}
                LEFT JOIN {self.t('INVOICE', donem)} INV{self.nl} ON INV.LOGICALREF = STL.INVOICEREF
                {kosul}""", params)

    def fatura_sayisi(self):
        toplam = 0
        for donem in self.donemler:
            toplam += self.tek(f"SELECT COUNT(*) FROM {self.t('INVOICE', donem)}{self.nl}")[0]
        return toplam


def baglanti_test(ayarlar):
    try:
        with LogoKaynagi(ayarlar) as k:
            adet = k.fatura_sayisi()
            kaynak = 'Demo veritabanı' if k.mod == 'demo' else 'Logo'
            return True, (f"{kaynak} bağlantısı başarılı. Firma {k.firma}, dönem "
                          f"{', '.join(k.donemler)}: {adet:,} fatura bulundu.")
    except ImportError:
        return False, "pyodbc kütüphanesi yüklü değil. (pip install pyodbc)"
    except Exception as e:
        return False, f"Bağlantı hatası: {e}"
