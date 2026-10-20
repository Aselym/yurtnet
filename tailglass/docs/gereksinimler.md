# Değişmez gereksinimler (yönetici sunumu ses kaydı, 2026-10-18)

Bu liste bir kaidedir: arayüz ne kadar değişirse değişsin her madde çalışır ve
kolayca bulunur durumda kalmalı. Her tasarım değişikliğinden sonra bu listeyi
uygulamada tek tek kontrol et. Köşeli parantez = kayıttaki dakika.

Son kontrol: 2026-10-19 (arayüz yenilemesi sonrası).

## 1. Dönem raporu (ay sonu) [10:43–11:15]
- [x] O ay ne alındı (alış faturaları) — Dönem raporu > Alışlar; ayrıca Alışlar sayfası
- [x] O ay ne satıldı (lisans değil, her şey) — Dönem raporu > Satışlar; Satışlar sayfası
- [x] Dönem sonu stok durumu (adet ve tutar) — Dönem raporu üst akış: dönem başı + alış − SMM = dönem sonu

## 2. Ürünler / satışlar
- [x] Sayfanın üstünde tarih aralığı / dönem seçimi [15:13, 16:23, 25:50] — üst çubuk (hazır seçenekler + özel aralık + sürüklenebilir şerit)
- [x] Müşteri bazlı görünüm, satırın yanında + ile aç/kapa [26:13] — Satışlar > Gruplu > Müşteri
- [x] Satış tarihine göre sıralama [25:19] — Satışlar > Satır satır > Tarih başlığı
- [x] Ürün tipi / marka / grup kolonları [27:46–29:04] — Satışlar kolonları, Grupla: Marka/Kategori/Ürün türü
- [x] Dell için ayrı sekme [27:55] — Ürünler ve stok > "Dell" sekmesi (Ayarlar > Şirket > Sabit marka sekmeleri; varsayılan Dell)
- [x] Satış tarihinin yanında alış tarihi; depoda bekleme süresi [31:51–32:28] — Satışlar > Satır satır (Alış tarihi, Depoda bekleme)
- [x] USD ve TL tutar, işlem günündeki kurla [32:46–33:16] — üst çubuk ₺ TL / $ USD / İkisi
- [x] Filtrelenmiş tabloyu Excel ve PDF olarak indirme [31:00–31:42] — her tabloda "PDF", sayfa başında "Excel'e aktar"
- [x] Pivot tarzı gruplama ve kâr oranları [29:48–30:33] — Analiz (satır/kolon/ölçü seçimi, marj ölçüleri)
- [x] Veri 2 yılla sınırlı değil [25:13] — Ayarlar > Veri kaynağı > Veri başlangıç tarihi (boş = tüm geçmiş)

## 3. Gelir paneli (yönetici ekranı)
- [x] Gelir ikiye ayrılır: fiziksel ürün ve tekrarlayan [19:01–19:44] — Genel bakış özet kartı (tıklanınca satırlara iner)
- [x] Aylık grafik, üzerine gelince/tıklanınca rakam [20:09–20:18] — Genel bakış grafikleri
- [x] Ürün ve tekrarlayan gelir için iki ayrı grafik, tıklayınca detaya inme [20:38–21:12]
- [x] Süresi girilmemiş lisanslar görünür ve kapatılabilir [17:13–17:30] — Genel bakış > Dikkat isteyenler > Süresi girilmeli; Lisanslar > Süre girilmeli (satıra tıkla, süre seç)
- [x] İnternet hizmeti de tekrarlayan gelir [18:14–18:30] — Logo hizmet kartlarındaki internet/barındırma/bakım sözleşmesi hizmetleri "Tekrarlayan"; Ayarlar > Sınıflandırma ile değiştirilebilir. Gerçek Logo'daki hizmet adları canlıda doğrulanmalı.

## 3b. Analiz stüdyosu (açılış sayfası) — kullanıcı isteği, 2026-10-20
- [x] Açılışta sade, sunuma uygun bir çalışma alanı; karmaşık hazır analiz yok — Analiz stüdyosu
- [x] Veri bloklarını sürükleyip ızgaraya bırakarak kendi analizini kurma (Scratch benzeri)
- [x] Tarih aralığı, müşteri, ürün, lisans seçimini basit arayüzle kullanıcı yapar — sol panel
- [x] Grafiklere anında Türkçe yorum, "bu aralık önemli zira…" — sağ panel (kural tabanlı; yapay zekâ API'si sonra)
- [x] Not alma (analiz ve kart notu), kaydetme/açma, Excel (tüm analiz), grafiği görsel indirme, sunum modu
- [ ] Analiz hakkında yapay zekâ sohbeti — API anahtarı gelince

## 4. Lisans hatırlatmaları
- [x] Mailde uygulamaya link, tıklayınca o kayıt açılır [13:05] — Ayarlar > E-posta > Uygulama adresi
- [x] Bitişten önce kademeli hatırlatma, günler ayarlanabilir [12:35–12:49] — Ayarlar > Takip kuralları
- [x] Müşteriye onaylı mail / yenileme teklifi — Lisanslar satır düğmeleri; Teklifler

## 5. Abonelik sağlığı
- [x] Bağlı/yan firmaları eşleyebilme [34:12–34:49] — Müşteriler > firma kartı > Firma grubu; Ayarlar > Firma grupları

## 6. Erişim
- [x] Yalnızca şirket ağından erişim [14:20–14:33] — kurulum (DEPLOY.md), güvenlik duvarı

## Genel kaide (kullanıcı)
- Kontrol hep kullanıcıda: her çıktı kullanıcının seçtiği dönem, filtre ve kırılıma göre değişir; sabit eşik yok.
