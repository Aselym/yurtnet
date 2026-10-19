"""Veri kaynagi secici: Logo (MS SQL / demo), Excel-CSV ya da e-Fatura.

Hepsi ayni arayuzu verir (urunler, cariler, temsilciler, satirlar...);
warehouse.senkronize_et hangisinin acik oldugunu bilmeden calisir.
Yuklenen dosyalar veritabaninin yanindaki `kaynak_dosyalari/` klasorunde
durur — veri sirketin kendi sunucusundan cikmaz.
"""

import json
import os

from database import DB_PATH

KLASOR = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), 'kaynak_dosyalari')
DOSYA_KLASORU = os.path.join(KLASOR, 'tablo')
EFATURA_KLASORU = os.path.join(KLASOR, 'efatura')

KAYNAK_ADI = {'mssql': 'Logo', 'demo': 'Demo veri', 'dosya': 'Excel / CSV', 'efatura': 'e-Fatura'}


def esleme_ayari(ayarlar):
    try:
        return json.loads(ayarlar.get('dosya_esleme') or '{}')
    except ValueError:
        return {}


def kaynak_ac(ayarlar):
    mod = ayarlar.get('logo_source') or 'mssql'
    if mod == 'dosya':
        from kaynak_dosya import DosyaKaynagi
        e = esleme_ayari(ayarlar)
        if not e.get('dosya'):
            raise ValueError('Excel / CSV kaynağı seçili ama henüz dosya yüklenip eşleme kaydedilmedi.')
        return DosyaKaynagi(e, DOSYA_KLASORU)
    if mod == 'efatura':
        from kaynak_efatura import EFaturaKaynagi
        if not os.path.isdir(EFATURA_KLASORU) or not os.listdir(EFATURA_KLASORU):
            raise ValueError('e-Fatura kaynağı seçili ama henüz XML ya da ZIP dosyası yüklenmedi.')
        return EFaturaKaynagi(EFATURA_KLASORU, (ayarlar.get('efatura_vkn') or '').strip() or None)
    from logo_source import LogoKaynagi
    return LogoKaynagi(ayarlar)


def baglanti_test(ayarlar):
    mod = ayarlar.get('logo_source') or 'mssql'
    if mod in ('mssql', 'demo'):
        from logo_source import baglanti_test as logo_test
        return logo_test(ayarlar)
    try:
        with kaynak_ac(ayarlar) as k:
            satir = sum(1 for _ in k.satirlar())
            ek = f" Şirket vergi no: {k.sirket_vkn}." if mod == 'efatura' and getattr(k, 'sirket_vkn', None) else ''
            atla = f" {k.atlanan} satır tarih/ürün/tutar eksik olduğu için atlanacak." if getattr(k, 'atlanan', 0) else ''
            return True, f"{KAYNAK_ADI[mod]} okundu: {k.fatura_sayisi():,} fatura, {satir:,} satır.{ek}{atla}"
    except Exception as e:
        return False, str(e)
