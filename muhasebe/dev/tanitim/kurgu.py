"""Sahne karelerinden 1920x1080 altyazili kareler + tek parca anlatim sesi uretir."""
import json
import os
import re
import wave

from PIL import Image, ImageDraw, ImageFont

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, kurgu')
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(os.path.join(OUT, f))

W, H = 1920, 1080
SX, SY = 240, 22                     # ekran goruntusu konumu (1440x900, olceksiz = net)
ZEMIN = (20, 28, 25)
TURUNCU = (242, 105, 31)
FONT = C:/Windows/Fonts/segoeui.ttf'
FONT_B = C:/Windows/Fonts/segoeuib.ttf'
f_baslik = ImageFont.truetype(FONT_B, 26)
f_alt = ImageFont.truetype(FONT, 29)
f_no = ImageFont.truetype(FONT, 22)
f_kapak = ImageFont.truetype(FONT_B, 64)
f_kapak2 = ImageFont.truetype(FONT, 32)

ONCE, SONRA, KAPAK = 0.4, 0.7, 3.5
RATE = 16000

S = json.load(open(os.path.join(D, sahneler.json'), encoding='utf-8'))
kurgu, ses = [], []


def sessizlik(sn):
    return b\x00\x00' * int(sn * RATE)


def satirla(metin, font, genislik):
    kelimeler, satirlar, s = metin.split(), [], '
    d = ImageDraw.Draw(Image.new(RGB', (1, 1)))
    for k in kelimeler:
        aday = (s +  ' + k).strip()
        if d.textlength(aday, font=font) <= genislik:
            s = aday
        else:
            satirlar.append(s)
            s = k
    if s:
        satirlar.append(s)
    return satirlar


def parcala(metin):
    """Altyazi parcalari: en fazla 2 satira sigan cumle gruplari."""
    cumleler = re.split(r(?<=[.!?])\s+', metin.strip())
    ince = []
    for c in cumleler:
        if len(satirla(c, f_alt, 1440)) <= 2:
            ince.append(c)
        else:                                   # uzun cumle: noktali virgul/virgulden bol
            parca = '
            for p in re.split(r(?<=[;,])\s+', c):
                aday = (parca +  ' + p).strip()
                if parca and len(satirla(aday, f_alt, 1440)) > 2:
                    ince.append(parca)
                    parca = p
                else:
                    parca = aday
            if parca:
                ince.append(parca)
    birlesik, cur = [], '
    for c in ince:
        aday = (cur +  ' + c).strip()
        if cur and len(satirla(aday, f_alt, 1440)) > 2:
            birlesik.append(cur)
            cur = c
        else:
            cur = aday
    if cur:
        birlesik.append(cur)
    return birlesik


def kapak(baslik, alt, ad):
    im = Image.new(RGB', (W, H), ZEMIN)
    d = ImageDraw.Draw(im)
    d.rectangle([W // 2 - 60, 430, W // 2 + 60, 436], fill=TURUNCU)
    d.text((W // 2, 520), baslik, font=f_kapak, fill=(240, 244, 241), anchor=mm')
    d.text((W // 2, 600), alt, font=f_kapak2, fill=(170, 184, 177), anchor=mm')
    yol = os.path.join(OUT, ad)
    im.save(yol)
    return yol


def kare(sahne, no, altyazi):
    im = Image.new(RGB', (W, H), ZEMIN)
    ek = Image.open(sahne[png']).convert('RGB')
    v = sahne.get(vurgu')
    if v and v[2] > 4 and v[3] > 4:
        x, y, w, h = v
        p = 8
        kutu = [max(0, x - p), max(0, y - p), min(1440, x + w + p), min(900, y + h + p)]
        karart = Image.new(RGBA', ek.size, (10, 16, 13, 110))
        delik = ImageDraw.Draw(karart)
        delik.rounded_rectangle(kutu, radius=12, fill=(0, 0, 0, 0))
        ek = Image.alpha_composite(ek.convert(RGBA'), karart).convert('RGB')
        ImageDraw.Draw(ek).rounded_rectangle(kutu, radius=12, outline=TURUNCU, width=4)
    # ince cerceve + golge hissi
    im.paste(ek, (SX, SY))
    d = ImageDraw.Draw(im)
    d.rectangle([SX - 1, SY - 1, SX + 1440, SY + 900], outline=(52, 64, 58), width=1)
    y0 = SY + 900 + 16
    d.text((SX, y0), sahne[baslik'], font=f_baslik, fill=TURUNCU)
    d.text((SX + 1440, y0 + 3), f{no} / {len(S)}', font=f_no, fill=(120, 136, 128), anchor='ra')
    for i, satir in enumerate(satirla(altyazi, f_alt, 1440)[:2]):
        d.text((SX, y0 + 38 + i * 38), satir, font=f_alt, fill=(236, 241, 238))
    return im


# --- kapak
kurgu.append({png': kapak('Piramit Lisans Takip', 'Satış, stok, analiz ve lisans takibi — uygulama tanıtımı', '000.png'), 'sure': KAPAK})
ses.append(sessizlik(KAPAK))

n = 0
for no, s in enumerate(S, 1):
    w = wave.open(os.path.join(D, ses', f'{no:02d}.wav'))
    assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
    pcm = w.readframes(w.getnframes())
    konusma = w.getnframes() / RATE
    toplam = ONCE + konusma + SONRA
    ses.append(sessizlik(ONCE) + pcm + sessizlik(SONRA))
    parcalar = parcala(s[metin'])
    agirlik = [len(p) for p in parcalar]
    for i, p in enumerate(parcalar):
        sure = konusma * agirlik[i] / sum(agirlik)
        if i == 0:
            sure += ONCE
        if i == len(parcalar) - 1:
            sure += SONRA
        n += 1
        yol = os.path.join(OUT, f{n + 0:03d}s.png')
        kare(s, no, p).save(yol)
        kurgu.append({png': yol, 'sure': round(sure, 3)})

kurgu.append({png': kapak('Teşekkürler', 'Kurulum adımları DEPLOY.md dosyasında', 'zzz.png'), 'sure': KAPAK})
ses.append(sessizlik(KAPAK))

with wave.open(os.path.join(D, anlatim.wav'), 'wb') as o:
    o.setnchannels(1)
    o.setsampwidth(2)
    o.setframerate(RATE)
    o.writeframes(b'.join(ses))
json.dump(kurgu, open(os.path.join(D, kurgu.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print(len(kurgu), kare,', round(sum(k['sure'] for k in kurgu), 1), 'sn')
