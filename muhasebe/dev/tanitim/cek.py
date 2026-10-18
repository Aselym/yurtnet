"""Demo sunucudan (5050) sahne sahne ekran goruntusu + vurgu kutusu + anlatim metni toplar."""
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

B = 'http://localhost:5050'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kare')
os.makedirs(OUT, exist_ok=True)
SAHNELER = []


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(channel='msedge', headless=True)
        ctx = br.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=1, locale='tr-TR')
        pg = ctx.new_page()
        pg.set_default_timeout(15000)

        def bekle(s=1.2):
            try:
                pg.wait_for_load_state('networkidle', timeout=8000)
            except Exception:
                pass
            time.sleep(s)

        def kutu(loc):
            try:
                b = loc.first.bounding_box()
                if b:
                    return [b['x'], b['y'], b['width'], b['height']]
            except Exception:
                pass
            return None

        def sahne(baslik, metin, vurgu=None):
            n = len(SAHNELER) + 1
            yol = os.path.join(OUT, f'{n:02d}.png')
            vk = kutu(vurgu) if vurgu is not None else None
            pg.screenshot(path=yol)
            SAHNELER.append({'png': yol, 'baslik': baslik, 'metin': metin, 'vurgu': vk})
            print(n, baslik, flush=True)

        def git(sayfa):
            pg.goto(f'{B}/#/{sayfa}')
            bekle(1.8)
            pg.mouse.move(5, 890)

        def adim(f):
            try:
                f()
            except Exception as e:
                print('  !! adim atlandi:', repr(e)[:160], flush=True)

        # ------------------------------------------------------------ giris
        pg.goto(B)
        bekle()
        sahne('Giriş', 'Bu video, Logo verisiyle çalışan satış, stok ve lisans takip uygulamasını baştan sona tanıtıyor. '
              'Uygulama şirket ağındaki sunucuda çalışır, tarayıcıdan kullanıcı adı ve şifreyle girilir.')
        pg.locator('input').nth(0).fill('admin')
        pg.locator('input[type=password]').fill('Aa123456')
        pg.keyboard.press('Enter')
        bekle(2.5)

        # ------------------------------------------------------------ donem
        def son12():
            pg.get_by_text('Dönem', exact=True).first.click()
            time.sleep(0.6)
            pg.get_by_role('button', name='Son 12 ay').click()
            bekle(2)
        adim(son12)
        pg.mouse.move(5, 890)
        sahne('Genel bakış', 'Açılış ekranı genel bakış. Solda seçili dönemin net satışı büyük yazılır; kuruş gösterilmez, altında rakamın Türkçe okunuşu yer alır. '
              'Sağda alış, brüt kâr, kâr marjı, fatura, müşteri ve ürün çeşidi sayısı; her birinin altında önceki döneme göre değişim oku bulunur.',
              pg.locator('section.panel').first)
        adim(lambda: pg.get_by_text('Dönem', exact=True).first.click())
        time.sleep(0.8)
        sahne('Dönem seçimi', 'Her ekran, üst çubuktaki dönem seçimine göre hesaplanır. Bu ay, geçen çeyrek, yılbaşından bugüne '
              'gibi hazır seçenekler var; isterseniz başlangıç ve bitiş tarihini kendiniz girersiniz.',
              pg.locator('div.z-40.rounded-xl').first)
        pg.keyboard.press('Escape')
        time.sleep(0.4)
        sahne('Zaman şeridi', 'Dönem kutusunun yanındaki şerit, tüm yılların aylık satışını gösterir. Fareyle sürükleyerek '
              'istediğiniz ay aralığını seçebilirsiniz; seçim bütün sayfalara aynı anda uygulanır.',
              pg.locator('svg').filter(has=pg.locator('rect')).first)
        adim(lambda: pg.get_by_role('radio', name='İkisi').click())
        bekle(1.5)
        sahne('TL ve USD', 'Para birimi düğmesiyle tutarları Türk lirası, dolar ya da ikisi birden görebilirsiniz. Dolar karşılığı, '
              'Logo\'daki işlem günü kuruyla hesaplanır; böylece enflasyondan arınmış karşılaştırma yapılır.',
              pg.get_by_role('radiogroup').first)
        adim(lambda: pg.get_by_role('radio', name='₺ TL').click())
        bekle(1)
        pg.locator('main').evaluate('m => m.scrollTo(0, 560)')
        time.sleep(1)
        sahne('Ürün ve tekrarlayan gelir', 'Satış, ürün satışı ve tekrarlayan gelir olarak ikiye ayrılır ve ayrı grafiklerde izlenir. Eksenler yuvarlak değerlerle yazılır; '
              'bir çubuğun üzerine gelince o dönemin tam tutarı görünür, tıklayınca dönem o aralığa daralır.')
        pg.locator('main').evaluate('m => m.scrollTo(0, 1250)')
        time.sleep(1)
        sahne('Alış ve satış, sıralamalar', 'Alış ve satış eğrisi aynı grafikte karşılaştırılır. Altında marka ve kategori sıralamaları, seçili dönemde en çok satılanları '
              've kâr marjlarını gösterir. Bir satıra tıklamak o değeri filtre olarak ekler.')
        pg.locator('main').evaluate('m => m.scrollTo(0, 2300)')
        time.sleep(1)
        sahne('Müşteri ve temsilci sıralaması', 'Aynı şekilde en çok alan müşteriler ve temsilcilerin satışları sıralanır; '
              'her satırda tutar ve kâr marjı yazar.')
        pg.locator('main').evaluate('m => m.scrollTo(0, 0)')

        # ------------------------------------------------------------ filtre
        def filtre():
            pg.get_by_role('button', name='Filtre ekle').first.click()
            time.sleep(0.8)
            pg.get_by_role('button', name='Marka', exact=True).click()
            bekle(1.5)
            pg.get_by_text('Microsoft', exact=True).first.click()
            pg.get_by_role('radio', name='Hariç').click()
            time.sleep(0.5)
        adim(filtre)
        sahne('Filtre ekleme', 'Filtre ekle düğmesiyle marka, kategori, müşteri, temsilci, şehir gibi her boyuta filtre koyulur. '
              'Dahil ya da hariç seçilebilir; örneğin Microsoft dışındaki her şey.', pg.locator('div.z-40.rounded-xl').first)
        adim(lambda: (pg.get_by_role('button', name='Uygula').click(), bekle(2)))
        sahne('Filtre uygulandı', 'Uygulanan filtre bir etiket olarak görünür ve tüm sayfalara taşınır. Etiketin çarpısıyla kaldırılır.',
              pg.get_by_role('button', name='filtresini kaldır').first)
        adim(lambda: (pg.get_by_role('button', name='filtresini kaldır').first.click(), bekle(1)))

        # ------------------------------------------------------------ satislar
        git('satislar')
        sahne('Satışlar', 'Satışlar sayfası Logo\'daki satış faturası satırlarını gösterir. Üstte tutar, adet, fatura, müşteri, '
              'FIFO yöntemiyle tahmini brüt kâr ve ürünün depoda ortalama kaç gün beklediği yer alır. İadeler düşülmüş ya da brüt görülebilir.')
        adim(lambda: (pg.locator('[role=row]').nth(1).click(), bekle(1.5)))
        pg.locator('main').evaluate('m => m.scrollTo(0, 380)')
        time.sleep(0.8)
        sahne('Gruplu görünüm', 'Gruplu görünümde satırlar müşteri, marka, kategori, temsilci, şehir ya da aya göre toplanır. '
              'Bir grubu açınca içindeki faturalar listelenir.')
        adim(lambda: (pg.get_by_role('radio', name='Satır satır').click(), bekle(1.5)))
        adim(lambda: (pg.get_by_placeholder('Ürün, müşteri, fiş no ara').fill('latitude'), bekle(2)))
        sahne('Satır satır ve arama', 'Satır satır görünümde her fatura satırı tek tek görünür. Arama kutusu ürün, müşteri ve fiş '
              'numarasında arar; üstteki toplamlar aramaya göre yeniden hesaplanır.', pg.get_by_placeholder('Ürün, müşteri, fiş no ara'))
        adim(lambda: (pg.get_by_role('button', name='Kolonlar').first.click(), time.sleep(0.8)))
        sahne('Kolon seçimi ve Excel', 'Kolonlar menüsünden hangi bilgilerin görüneceğini seçersiniz; seçim hatırlanır. Excel\'e aktar '
              'düğmesi ekranda ne görüyorsanız aynı filtre ve kolonlarla Excel dosyası üretir; ilk sayfada raporun dönemi ve filtreleri yazar.')
        pg.keyboard.press('Escape')

        git('alislar')
        sahne('Alışlar', 'Alışlar sayfası aynı yapıdadır: hangi tedarikçiden, ne zaman, hangi fiyata alındığı. '
              'Tutarlar hem lira hem işlem günündeki dolar karşılığıyla izlenir.')

        # ------------------------------------------------------------ stok
        git('stok')
        sahne('Ürünler ve stok', 'Stok sayfası eldeki ürünleri, değerini ve ölü stoğu gösterir. Ölü stok, uzun süredir hareket '
              'görmeyen ürünlerin bağladığı paradır. Tarih kutusuna geçmiş bir gün yazarsanız o günkü stok durumu hesaplanır.')
        adim(lambda: (pg.locator('[role=row]').nth(1).click(), bekle(2)))
        sahne('Ürün geçmişi', 'Bir ürüne tıklayınca son üç yılın aylık alış ve satış adetleri ile tüm hareketleri açılır: '
              'kimden alındı, kime satıldı, satılan ürün hangi tarihteki alıştan karşılandı.')
        pg.keyboard.press('Escape')
        adim(lambda: (pg.get_by_role('radio', name='Ürün performansı').click(), bekle(2)))
        sahne('Ürün performansı', 'Ürün performansı sekmesi seçili dönemde ürün bazında satış, adet ve kârı sıralar. '
              'Sık baktığınız marka ya da kategorileri sekme olarak sabitleyebilirsiniz.')

        # ------------------------------------------------------------ musteriler
        git('musteriler')
        sahne('Müşteriler', 'Müşteriler sayfası seçili dönemde kim ne kadar aldı ve ne kadar kâr bıraktı sorusunu cevaplar. '
              'Aynı patrona ait firmalar firma grubu olarak birleştirilip birlikte izlenebilir.')
        adim(lambda: (pg.locator('[role=row]').nth(1).click(), bekle(2.5)))
        sahne('Müşteri kartı', 'Bir müşteriye tıklayınca tüm zamanların toplamı, aylık alımları, hangi kategori ve markalardan aldığı, '
              'en çok aldığı ürünler ve lisanslarının durumu tek ekranda açılır.')
        pg.keyboard.press('Escape')

        # ------------------------------------------------------------ analiz
        git('analiz')
        sahne('Analiz', 'Analiz sayfası programın en esnek bölümüdür. Satırlara, kolonlara ve ölçülere ne koyacağınızı siz seçersiniz; '
              'yukarıdaki hazır örneklerle de başlayabilirsiniz.', pg.locator('aside').first)
        pg.locator('main').evaluate('m => m.scrollTo(0, 900)')
        time.sleep(1.2)
        sahne('Pivot tablo', 'Örneğin kategori satırlara, çeyrek kolonlara konunca tablo yan yana açılır. Isı haritası büyük değerleri '
              'koyulaştırır. Kolon sayısı fazlaysa en eski dönemler Daha eski başlığında toplanır; bu sınırı da siz belirlersiniz.')
        adim(lambda: (pg.get_by_role('button', name='Marka bazında kâr ve marj').click(), bekle(2)))
        adim(lambda: (pg.get_by_role('radio', name='Grafik').click(), bekle(1.5)))
        pg.locator('main').evaluate('m => m.scrollTo(0, 900)')
        time.sleep(1)
        sahne('Grafik görünümü', 'Aynı sonuç grafik olarak da görülebilir. Kurduğunuz görünümü bir isimle kaydedip daha sonra tek '
              'tıkla açabilir, Excel\'e aktarabilirsiniz.')

        # ------------------------------------------------------------ donem raporu
        git('donem')
        adim(lambda: (pg.get_by_role('button', name='Eylül').first.click(), bekle(2.5)))
        sahne('Dönem raporu', 'Dönem raporu, ay sonu kapanışı için hazırlanmıştır. Dönem başı stok artı alışlar eksi satılan malın maliyeti, '
              'dönem sonu stoğu verir. Altında satış, kâr, fatura sayıları ve dolar karşılıkları bulunur.')
        pg.locator('main').evaluate('m => m.scrollTo(0, 700)')
        time.sleep(1)
        sahne('Rapor tablosu', 'Rapor kategori, marka, ürün türü ya da gelir tipine göre kırılabilir. Yazdırma ve Excel düğmeleriyle '
              'muhasebeye hazır çıktı alınır.')

        # ------------------------------------------------------------ lisanslar
        git('lisanslar')
        sahne('Lisanslar', 'Lisanslar sayfası WatchGuard, FortiGate, ESET gibi süreli lisansları bitiş tarihine göre izler. '
              'Üstte yakında dolacaklar, beklenen yenileme geliri ve süresi girilmesi gerekenler yer alır.')
        pg.locator('main').evaluate('m => m.scrollTo(0, 330)')
        time.sleep(0.8)
        sahne('Yenileme adayları', 'Süresi dolan bir lisansın yerine aynı müşteriye benzer bir ürün satılmışsa program bunu yenileme adayı '
              'olarak gösterir. Yenilendi ya da değil diyerek onaylarsınız; emin olunmayan hiçbir kayıt kendiliğinden kapanmaz.')
        def sure():
            pg.get_by_role('radio', name='Süre girilmeli').click()
            bekle(1.2)
            pg.locator('[role=row]').nth(1).click()
            time.sleep(1)
        adim(sure)
        sahne('Süre girme', 'Ürün adından süresi anlaşılamayan lisanslar süre girilmeli sekmesinde bekler. Satıra tıklayıp bir, iki, üç '
              'ya da beş yıl seçmeniz yeterli. Hatırlatma e-postaları bitişten on, beş ve bir gün önce ekibe gider; bu günler ayarlardan değişir.')
        pg.keyboard.press('Escape')

        git('abonelikler')
        sahne('Abonelikler', 'Abonelikler sayfası Microsoft 365, Azure gibi aylık faturalanan hizmetleri izler. Her müşterinin kendi '
              'faturalama aralığına göre gecikme hesaplanır; riskli ve kayıp aboneler ayrı sekmelerde görünür.')
        git('teklifler')
        sahne('Teklifler', 'Teklifler sayfasında Logo\'ya henüz düşmeyen yenileme teklifleri kaydedilir; kabul ya da ret durumu '
              'tek tıkla güncellenir ve kazanma oranı hesaplanır.')
        git('temsilciler')
        sahne('Temsilciler', 'Temsilciler sayfası her satış temsilcisinin cirosunu, kârını, marjını ve aylık dağılımını gösterir.')

        # ------------------------------------------------------------ ayarlar
        git('ayarlar')
        sahne('Ayarlar: veri kaynağı', 'Ayarlarda Logo bağlantısı, verinin hangi tarihten itibaren çekileceği ve otomatik senkron saatleri '
              'belirlenir. Veri başlangıcı boş bırakılırsa Logo\'daki tüm geçmiş alınır.')
        adim(lambda: (pg.get_by_role('button', name='Takip kuralları').click(), bekle(1)))
        sahne('Ayarlar: takip kuralları', 'Takip kurallarında hatırlatma günleri, yakında dolacak sayılan gün sayısı ve abonelik risk '
              'eşikleri ayarlanır. Programdaki sabit görünen her eşik buradan değiştirilebilir.')
        adim(lambda: (pg.get_by_role('button', name='Sınıflandırma').click(), bekle(1.5)))
        sahne('Ayarlar: sınıflandırma', 'Sınıflandırma bölümünde marka ve kategorisi yanlış tahmin edilen ürünler listelenir. Tek tıkla kural '
              'eklenir; kural Logo kartından ve sözlükten önce gelir ve geçmiş verinin tamamına uygulanır.')
        adim(lambda: (pg.get_by_role('button', name='Şirket ve görünüm').click(), bekle(1)))
        sahne('Ayarlar: şirket', 'Şirket adı, uygulama adı, marka rengi ve e-postalardaki bağlantı adresi buradan değişir. Aynı program '
              'Pusula adıyla başka işletmeler için de hazırlandı.')

        # ------------------------------------------------------------ koyu tema + kapanis
        git('genel')
        adim(lambda: (pg.locator('button[title="Koyu tema"]').first.click(), time.sleep(1)))
        sahne('Koyu tema', 'Sol alttaki düğmeyle açık ve koyu tema arasında geçilir. Tercih her kullanıcının tarayıcısında hatırlanır.')
        sahne('Özet', 'Özetle: veri Logo\'dan salt okunur şekilde günde birkaç kez çekilir, kontrol tamamen kullanıcıdadır ve her ekran '
              'Excel\'e aktarılabilir. İzlediğiniz için teşekkürler.')

        br.close()
    with open(os.path.join(os.path.dirname(OUT), 'sahneler.json'), 'w', encoding='utf-8') as f:
        json.dump(SAHNELER, f, ensure_ascii=False, indent=1)
    print('bitti', len(SAHNELER))


if __name__ == '__main__':
    sys.exit(main())
