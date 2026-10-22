"""Yapay zekanin sirket verisine erisimi: arka plan profili, salt-okunur araclar, ad maskeleme.

Model Logo'ya ya da veritabanina dogrudan baglanmaz. Senkronla ambara gelen
veriyi iki yoldan gorur:
  1. sirket_profili(): her konusmada verilen ozet (aylik seyir, buyuk musteriler,
     markalar, lisans/abonelik durumu, stok). "Arka plan bilgisi".
  2. ai_araclar.py: modelin kendi calistirdigi beyaz listeli, salt-okunur sorgular.

ai_mask_names = ON iken musteri ve temsilci adlari modele "Müşteri #123" olarak
gider; modelin cevabinda ve arac argumanlarinda gercek ada geri cevrilir.
"""
import re
import zlib
from datetime import date, timedelta

import analytics
from database import get_db_connection

def _bugun():
    return date.today().isoformat()


def _gun_once(n):
    return (date.today() - timedelta(days=n)).isoformat()


def _yuvarla(v):
    if isinstance(v, float):
        return round(v, 1) if abs(v) < 100 else round(v)
    return v


# ------------------------------------------------------------------ maskeleme
class Maske:
    """Gercek ad <-> takma ad. Takma adlar kalici (cari/temsilci numarasina bagli)."""

    def __init__(self, acik):
        self.acik = acik
        self.gercek_takma, self.takma_gercek = {}, {}
        if not acik:
            return
        conn = get_db_connection()
        try:
            for r in conn.execute("SELECT client_ref, name FROM wh_clients WHERE name IS NOT NULL AND name <> ''"):
                self._ekle(r['name'], f"Müşteri #{r['client_ref']}")
            for i, r in enumerate(conn.execute("SELECT DISTINCT group_name FROM client_groups WHERE group_name <> ''"), 1):
                self._ekle(r['group_name'], f"Firma grubu #{i}")
            for r in conn.execute("SELECT salesman_ref, name FROM wh_salesmen WHERE name IS NOT NULL AND name <> ''"):
                self._ekle(r['name'], f"Temsilci #{r['salesman_ref']}")
            for r in conn.execute("SELECT DISTINCT sales_rep FROM sales WHERE sales_rep <> ''"):
                self._ekle(r['sales_rep'], f"Temsilci #{zlib.crc32(r['sales_rep'].encode()) % 9000 + 1000}")
        except Exception:
            pass
        finally:
            conn.close()
        self._ileri = self._desen(self.gercek_takma)
        self._geri = self._desen(self.takma_gercek)

    def _ekle(self, gercek, takma):
        gercek = (gercek or '').strip()
        if len(gercek) < 3 or gercek in self.gercek_takma:
            return
        while takma in self.takma_gercek:
            takma += "'"
        self.gercek_takma[gercek] = takma
        self.takma_gercek[takma] = gercek

    @staticmethod
    def _desen(sozluk):
        if not sozluk:
            return None
        return re.compile('|'.join(re.escape(k) for k in sorted(sozluk, key=len, reverse=True)))

    def gizle(self, metin):
        if not self.acik or not self._ileri or not metin:
            return metin
        return self._ileri.sub(lambda m: self.gercek_takma[m.group(0)], metin)

    # Model takma adi bazen kisaltir: "temsilci #3", "#656". Bunlar da numarasindan geri acilir.
    _TEMSILCI_KISA = re.compile(r'(?i)\btemsilci\s*#\s*(\d+)')
    _MUSTERI_KISA = re.compile(r'(?i)(?:\bmüşteri\s*)?(?<![\w#])#\s*(\d+)\b')

    def ac(self, metin):
        if not self.acik or not self._geri or not metin:
            return metin
        metin = self._geri.sub(lambda m: self.takma_gercek[m.group(0)], metin)
        metin = self._TEMSILCI_KISA.sub(lambda m: self.takma_gercek.get(f'Temsilci #{m.group(1)}', m.group(0)), metin)
        return self._MUSTERI_KISA.sub(lambda m: self.takma_gercek.get(f'Müşteri #{m.group(1)}', m.group(0)), metin)

    def ac_deger(self, v):
        """Arac argumanindaki takma adi gercege cevirir (liste/dict icinde de)."""
        if isinstance(v, str):
            return self.ac(v)
        if isinstance(v, list):
            return [self.ac_deger(x) for x in v]
        if isinstance(v, dict):
            return {k: self.ac_deger(x) for k, x in v.items()}
        return v


# ------------------------------------------------------------------ arka plan profili
_PROFIL = {'anahtar': None, 'metin': ''}


def sirket_profili():
    """Yaklasik 2-3 bin token'lik sirket ozeti (duz metin). Son senkron ve gun degismedikce onbellekten."""
    ar = analytics.veri_araligi()
    anahtar = (_bugun(), ar.get('lines'), (ar.get('last_sync') or {}).get('id'))
    if _PROFIL['anahtar'] != anahtar:
        _PROFIL['metin'] = _profil_uret(ar)
        _PROFIL['anahtar'] = anahtar
    return _PROFIL['metin']


def _profil_uret(ar):
    if not ar.get('lines'):
        return 'Ambarda henüz veri yok (senkron yapılmamış).'
    L = [f"Bugün: {_bugun()}. Ambardaki veri: {ar['first']} – {ar['last']}, {ar['lines']:,} hareket satırı."]
    s = ar.get('last_sync') or {}
    if s.get('finished_at'):
        L.append(f"Son senkron: {s['finished_at']} (kaynak: {s.get('source')}).")
    yil_once, bas13 = _gun_once(365), _gun_once(395)

    def q(**istek):
        return analytics.sorgu(istek)

    ay = q(group_by=['month'], measures=['net_tl', 'profit_tl', 'margin', 'clients'], date_from=bas13, sort={'key': 'd0', 'desc': False})
    L.append('\nAylık net satış (TL), brüt kâr (TL), kâr marjı (%), müşteri sayısı — son 13 ay:')
    L += [f"{r['d0']}: {r['m_net_tl'] or 0:,.0f} | {r['m_profit_tl'] or 0:,.0f} | {(r['m_margin'] or 0):.1f} | {r['m_clients']}" for r in ay['rows']]
    alis = q(group_by=['month'], measures=['net_tl'], direction='ALIS_NET', date_from=yil_once, sort={'key': 'd0', 'desc': False})
    L.append('\nAylık alış (TL) — son 12 ay: ' + ', '.join(f"{r['d0']} {r['m_net_tl'] or 0:,.0f}" for r in alis['rows']))

    for boyut, ad, n in (('client', 'En büyük müşteriler', 10), ('brand', 'Markalar', 8), ('category', 'Kategoriler', 8),
                         ('salesman', 'Temsilciler', 8), ('revenue_type', 'Gelir tipleri', 4)):
        r = q(group_by=[boyut], measures=['net_tl', 'profit_tl', 'margin'], date_from=yil_once, limit=n)
        toplam = r['totals'].get('m_net_tl') or 0
        L.append(f"\n{ad} — son 12 ay (net TL | kâr TL | marj % | pay %):")
        L += [f"{x['d0']}: {x['m_net_tl'] or 0:,.0f} | {x['m_profit_tl'] or 0:,.0f} | {(x['m_margin'] or 0):.1f} | "
              f"{(100 * (x['m_net_tl'] or 0) / toplam if toplam else 0):.1f}" for x in r['rows']]

    conn = get_db_connection()
    try:
        bugun, ufuk = _bugun(), (date.today() + timedelta(days=90)).isoformat()
        yakin = conn.execute("""SELECT client_name, product_name, expiration_date, price FROM sales
                                WHERE status = 'PENDING' AND expiration_date BETWEEN ? AND ? ORDER BY expiration_date LIMIT 8""",
                             (bugun, ufuk)).fetchall()
        sayilar = dict(conn.execute("SELECT status, COUNT(*) FROM sales GROUP BY status").fetchall())
        L.append(f"\nLisanslar: takipte {sayilar.get('PENDING', 0)}, süresi geçmiş {sayilar.get('EXPIRED', 0)}, "
                 f"yenilenmiş {sayilar.get('RENEWED', 0)}, süresi girilmeli {sayilar.get('NEEDS_DURATION', 0)}.")
        if yakin:
            L.append('90 gün içinde dolacak lisanslar (müşteri | ürün | bitiş | satış fiyatı TL):')
            L += [f"{r[0]} | {r[1]} | {r[2]} | {r[3] or 0:,.0f}" for r in yakin]
        abone = conn.execute("""SELECT client_name, product_name, status, days_since_last, avg_interval_days FROM subscriptions
                                WHERE status IN ('AT_RISK','LOST') ORDER BY days_since_last LIMIT 8""").fetchall()
        sayi = dict(conn.execute("SELECT status, COUNT(*) FROM subscriptions GROUP BY status").fetchall())
        L.append(f"\nAbonelikler: aktif {sayi.get('ACTIVE', 0)}, riskli {sayi.get('AT_RISK', 0)}, kayıp {sayi.get('LOST', 0)}.")
        if abone:
            L.append('Riskli/kayıp abonelikler (müşteri | ürün | durum | son faturadan beri gün | normal aralık gün):')
            L += [f"{r[0]} | {r[1]} | {'riskli' if r[2] == 'AT_RISK' else 'kayıp'} | {r[3]} | {r[4]:.0f}" for r in abone]
    finally:
        conn.close()

    try:
        gruplar, toplam = analytics.stok_grup_ozeti(_bugun())
        L.append(f"\nBugünkü stok değeri: {toplam.get('value_tl', 0) or 0:,.0f} TL. Kategoriye göre (TL): " +
                 ', '.join(f"{k} {v['value_tl']:,.0f}" for k, v in sorted(gruplar.items(), key=lambda x: -x[1]['value_tl'])[:8]))
    except Exception:
        pass
    return '\n'.join(L)
