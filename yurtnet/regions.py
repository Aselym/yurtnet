"""Host adından il ve coğrafi bölge çıkarımı.

Zabbix'te bölge etiketi tanımlı olmadığı için bölge bilgisi host adındaki
il adından türetilir (ör. TUGVA-TRABZON-M300 -> Trabzon -> Karadeniz).
Zabbix'e sonradan `bolge` etiketi eklenirse o öncelikli olur.
"""

from __future__ import annotations

import re

# Türkçe karakterleri ASCII'ye indirger; host adları zaten ASCII yazılmış.
_TR_MAP = str.maketrans(
    "ÇĞİıÖŞÜçğiöşü",
    "CGIIOSUcgiosu",
)

SEPARATORS = re.compile(r"[-_.\s]+")

# İl -> coğrafi bölge (81 il).
PROVINCE_REGION: dict[str, str] = {
    # Marmara
    "ISTANBUL": "Marmara", "BURSA": "Marmara", "KOCAELI": "Marmara",
    "SAKARYA": "Marmara", "YALOVA": "Marmara", "CANAKKALE": "Marmara",
    "BALIKESIR": "Marmara", "TEKIRDAG": "Marmara", "EDIRNE": "Marmara",
    "KIRKLARELI": "Marmara", "BILECIK": "Marmara",
    # Ege
    "IZMIR": "Ege", "AYDIN": "Ege", "MANISA": "Ege", "DENIZLI": "Ege",
    "MUGLA": "Ege", "AFYONKARAHISAR": "Ege", "AFYON": "Ege",
    "KUTAHYA": "Ege", "USAK": "Ege",
    # Akdeniz
    "ANTALYA": "Akdeniz", "ADANA": "Akdeniz", "MERSIN": "Akdeniz",
    "ICEL": "Akdeniz", "HATAY": "Akdeniz", "ISPARTA": "Akdeniz",
    "BURDUR": "Akdeniz", "KAHRAMANMARAS": "Akdeniz", "MARAS": "Akdeniz",
    "OSMANIYE": "Akdeniz",
    # İç Anadolu
    "ANKARA": "İç Anadolu", "KONYA": "İç Anadolu", "KAYSERI": "İç Anadolu",
    "SIVAS": "İç Anadolu", "KIRSEHIR": "İç Anadolu", "ESKISEHIR": "İç Anadolu",
    "AKSARAY": "İç Anadolu", "KARAMAN": "İç Anadolu", "KIRIKKALE": "İç Anadolu",
    "NEVSEHIR": "İç Anadolu", "NIGDE": "İç Anadolu", "YOZGAT": "İç Anadolu",
    "CANKIRI": "İç Anadolu",
    # Karadeniz
    "TRABZON": "Karadeniz", "SAMSUN": "Karadeniz", "SINOP": "Karadeniz",
    "KASTAMONU": "Karadeniz", "BOLU": "Karadeniz", "ORDU": "Karadeniz",
    "GIRESUN": "Karadeniz", "RIZE": "Karadeniz", "ARTVIN": "Karadeniz",
    "GUMUSHANE": "Karadeniz", "BAYBURT": "Karadeniz", "AMASYA": "Karadeniz",
    "TOKAT": "Karadeniz", "CORUM": "Karadeniz", "ZONGULDAK": "Karadeniz",
    "BARTIN": "Karadeniz", "KARABUK": "Karadeniz", "DUZCE": "Karadeniz",
    # Doğu Anadolu
    "ERZURUM": "Doğu Anadolu", "ERZINCAN": "Doğu Anadolu", "ELAZIG": "Doğu Anadolu",
    "MALATYA": "Doğu Anadolu", "VAN": "Doğu Anadolu", "KARS": "Doğu Anadolu",
    "AGRI": "Doğu Anadolu", "ARDAHAN": "Doğu Anadolu", "IGDIR": "Doğu Anadolu",
    "BINGOL": "Doğu Anadolu", "BITLIS": "Doğu Anadolu", "MUS": "Doğu Anadolu",
    "TUNCELI": "Doğu Anadolu", "HAKKARI": "Doğu Anadolu",
    # Güneydoğu Anadolu
    "GAZIANTEP": "Güneydoğu", "SANLIURFA": "Güneydoğu", "URFA": "Güneydoğu",
    "DIYARBAKIR": "Güneydoğu", "ADIYAMAN": "Güneydoğu", "MARDIN": "Güneydoğu",
    "BATMAN": "Güneydoğu", "SIIRT": "Güneydoğu", "SIRNAK": "Güneydoğu",
    "KILIS": "Güneydoğu",
}

# İstanbul ilçeleri — host adlarında il yerine ilçe geçiyor.
DISTRICT_PROVINCE: dict[str, str] = {
    "FLORYA": "ISTANBUL", "GUNGOREN": "ISTANBUL", "USKUDAR": "ISTANBUL",
    "KADIKOY": "ISTANBUL", "FATIH": "ISTANBUL", "BESIKTAS": "ISTANBUL",
    "BAKIRKOY": "ISTANBUL", "SISLI": "ISTANBUL", "MALTEPE": "ISTANBUL",
    "PENDIK": "ISTANBUL", "KARTAL": "ISTANBUL", "BEYLIKDUZU": "ISTANBUL",
    "ESENYURT": "ISTANBUL", "AVCILAR": "ISTANBUL", "BAGCILAR": "ISTANBUL",
    "SULTANBEYLI": "ISTANBUL", "UMRANIYE": "ISTANBUL", "ATASEHIR": "ISTANBUL",
    "ZEYTINBURNU": "ISTANBUL", "EYUP": "ISTANBUL", "SARIYER": "ISTANBUL",
    "TUZLA": "ISTANBUL", "BEYOGLU": "ISTANBUL",
}


# Host adları ASCII yazılmış (KIRSEHIR); insana gösterilirken doğru Türkçe
# yazımı gerekiyor. Yalnızca ASCII'den farklı olanlar listelenir.
GORUNEN_AD: dict[str, str] = {
    "ISTANBUL": "İstanbul", "IZMIR": "İzmir", "AYDIN": "Aydın", "MUGLA": "Muğla",
    "CANAKKALE": "Çanakkale", "BALIKESIR": "Balıkesir", "TEKIRDAG": "Tekirdağ",
    "KIRKLARELI": "Kırklareli", "KUTAHYA": "Kütahya", "USAK": "Uşak",
    "KAHRAMANMARAS": "Kahramanmaraş", "MERSIN": "Mersin", "ISPARTA": "Isparta",
    "KIRSEHIR": "Kırşehir", "ESKISEHIR": "Eskişehir", "KIRIKKALE": "Kırıkkale",
    "NEVSEHIR": "Nevşehir", "NIGDE": "Niğde", "CANKIRI": "Çankırı",
    "CORUM": "Çorum", "KARABUK": "Karabük", "DUZCE": "Düzce",
    "GUMUSHANE": "Gümüşhane", "ELAZIG": "Elazığ", "BINGOL": "Bingöl",
    "AGRI": "Ağrı", "IGDIR": "Iğdır", "MUS": "Muş", "HAKKARI": "Hakkâri",
    "SANLIURFA": "Şanlıurfa", "URFA": "Şanlıurfa", "DIYARBAKIR": "Diyarbakır",
    "ADIYAMAN": "Adıyaman", "GAZIANTEP": "Gaziantep", "BITLIS": "Bitlis",
    "KASTAMONU": "Kastamonu", "MALATYA": "Malatya", "SAKARYA": "Sakarya",
    "SIRNAK": "Şırnak", "MARDIN": "Mardin", "SIVAS": "Sivas",
    # İstanbul ilçeleri ve yurt adlarında geçen ek parçalar
    "USKUDAR": "Üsküdar", "GUNGOREN": "Güngören", "KADIKOY": "Kadıköy",
    "SISLI": "Şişli", "EYUP": "Eyüp", "UMRANIYE": "Ümraniye",
    "ATASEHIR": "Ataşehir", "BESIKTAS": "Beşiktaş", "BAGCILAR": "Bağcılar",
    "BEYLIKDUZU": "Beylikdüzü", "SULTANBEYLI": "Sultanbeyli",
    "SEYH": "Şeyh", "DORT": "Dört", "UC": "Üç", "BESINCI": "Beşinci",
    "GUNEY": "Güney", "KUZEY": "Kuzey", "ISTIKLAL": "İstiklal",
}


def normalize(text: str) -> str:
    return text.translate(_TR_MAP).upper()


def gorunen(token: str) -> str:
    """Bir host adı parçasını insana gösterilecek biçime çevirir."""
    return GORUNEN_AD.get(normalize(token), token.capitalize())


def parse_host_name(host_name: str) -> tuple[str | None, str | None]:
    """Host adından (il, bölge) çıkarır. Bulunamazsa (None, None)."""
    for token in SEPARATORS.split(normalize(host_name)):
        if not token:
            continue
        province = DISTRICT_PROVINCE.get(token, token)
        region = PROVINCE_REGION.get(province)
        if region:
            return province.title(), region
    return None, None


def province_of(host_name: str) -> str | None:
    return parse_host_name(host_name)[0]


def region_of(host_name: str) -> str | None:
    return parse_host_name(host_name)[1]
