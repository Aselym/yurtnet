"""Senkron giris noktasi: Logo -> veri ambari -> lisans/abonelik/yenileme.

Eski surumde lisans, abonelik ve urunler icin Logo'ya uc ayri sorgu
atiliyordu (urunler son 2 yille sinirliydi). Artik tek bir senkron tum
hareket satirlarini ambara alir (baslangic tarihi kullanici ayari, bos ise
tum gecmis) ve her sey oradan turetilir. Ayrintilar: warehouse.py,
lisans_takip.py, siniflandirma.py.
"""

import threading

from database import get_settings
from kaynaklar import baglanti_test
import lisans_takip
import warehouse

# Ayni anda iki senkron (zamanlayici + "Simdi senkronize et" dugmesi) ambari
# yarim birakmasin.
_KILIT = threading.Lock()


def get_logo_settings():
    return get_settings()


def test_logo_connection():
    return baglanti_test(get_settings())


def tam_senkron(ilerleme=None):
    if not _KILIT.acquire(blocking=False):
        return {'success': False, 'message': 'Zaten bir senkron çalışıyor, birkaç saniye sonra tekrar deneyin.'}
    try:
        ayarlar = get_settings()
        ozet = warehouse.senkronize_et(ayarlar, ilerleme)
        eklenen, sure_bekleyen, _ = lisans_takip.lisanslari_turet(ayarlar)
        abone, riskli = lisans_takip.abonelikleri_turet(ayarlar)
        yenileme = lisans_takip.yenileme_adaylari_bul()
        ozet.update({'new_licenses': eklenen, 'needs_duration': sure_bekleyen, 'subscriptions': abone,
                     'at_risk': riskli, 'renewal_marks': yenileme})
        mesaj = (f"{ozet['lines']:,} hareket satırı, {ozet['items']:,} ürün, {ozet['clients']:,} cari aktarıldı "
                 f"({ozet['seconds']} sn). {eklenen} yeni lisans")
        if sure_bekleyen:
            mesaj += f" ({sure_bekleyen} tanesi için süre girilmeli)"
        mesaj += f", {abone} abonelik"
        if riskli:
            mesaj += f" ({riskli} riskli)"
        ozet.update({'success': True, 'message': mesaj + '.'})
        return ozet
    finally:
        _KILIT.release()


if __name__ == '__main__':
    import json
    ok, mesaj = test_logo_connection()
    print(mesaj)
    if ok:
        print(json.dumps(tam_senkron(print), ensure_ascii=False, indent=2))
