# Tanıtım videosu

Demo sunucu (`python dev/demo_sunucu.py`, port 5050) açıkken sırayla:

```
python cek.py                 # Edge ile sahne sahne ekran görüntüsü -> kare/, sahneler.json
powershell -File seslendir.ps1   # anlatımı Türkçe sesle (Microsoft Tolga) -> ses/
python kurgu.py               # 1080p altyazılı kareler + anlatim.wav -> kurgu/
powershell -File birlestir.ps1 -Cikti "C:\Claude 1\tanitim\muhasebe-tanitim.mp4"
```

Gerekenler: `pip install playwright pillow` (tarayıcı olarak kurulu Edge kullanılır),
Windows 10/11 (ses ve video Windows'un kendi motorlarıyla üretilir, ffmpeg gerekmez).
Anlatım metinleri `cek.py` içindeki `sahne(...)` çağrılarında; `sahneler.json` elle de düzenlenebilir.
