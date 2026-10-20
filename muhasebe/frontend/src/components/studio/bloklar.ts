/*
  Analiz Studyosu veri bloklari (Scratch esinli). Uc tur:
  - olcu  : "ne olculsun?"  (Satis tutari, kar, adet...) — kartin sayisi
  - boyut : "neye gore?"    (zaman, musteri, marka...)   — kartin kirilimi
  - hazir : tek tikla hazir filtre (lisanslar, tekrarlayan gelir...)
  Bloklar analiz motorunun beyaz listesindeki anahtarlari kullanir.
*/
import type { ColType, Direction } from '../../lib/api'

export type BlokTur = 'olcu' | 'boyut' | 'hazir'
export interface Blok {
  id: string; tur: BlokTur; ad: string; aciklama: string
  olcu?: string; yon?: Direction; tip?: ColType          // olcu bloklari
  boyut?: string; zaman?: boolean                        // boyut bloklari
  filtre?: Record<string, string[]>                      // hazir bloklar
}

export const OLCULER: Blok[] = [
  { id: 'satis', tur: 'olcu', ad: 'Satış', aciklama: 'İadeler düşülmüş satış tutarı (TL)', olcu: 'net_tl', yon: 'SATIS_NET', tip: 'tl' },
  { id: 'satis_usd', tur: 'olcu', ad: 'Satış $', aciklama: 'İşlem günündeki kurla USD satış', olcu: 'net_usd', yon: 'SATIS_NET', tip: 'usd' },
  { id: 'kar', tur: 'olcu', ad: 'Brüt kâr', aciklama: 'FIFO yöntemiyle tahmini brüt kâr (TL)', olcu: 'profit_tl', yon: 'SATIS_NET', tip: 'tl' },
  { id: 'marj', tur: 'olcu', ad: 'Kâr marjı', aciklama: 'Brüt kârın satışa oranı (%)', olcu: 'margin', yon: 'SATIS_NET', tip: 'pct' },
  { id: 'adet', tur: 'olcu', ad: 'Satılan adet', aciklama: 'Satılan ürün adedi', olcu: 'qty', yon: 'SATIS_NET', tip: 'num' },
  { id: 'alis', tur: 'olcu', ad: 'Alış', aciklama: 'İadeler düşülmüş alış tutarı (TL)', olcu: 'net_tl', yon: 'ALIS_NET', tip: 'tl' },
  { id: 'fatura', tur: 'olcu', ad: 'Fatura sayısı', aciklama: 'Kesilen satış faturası sayısı', olcu: 'invoices', yon: 'SATIS_NET', tip: 'num' },
  { id: 'musteri_say', tur: 'olcu', ad: 'Müşteri sayısı', aciklama: 'Alım yapan farklı müşteri sayısı', olcu: 'clients', yon: 'SATIS_NET', tip: 'num' },
  { id: 'bekleme', tur: 'olcu', ad: 'Depoda bekleme', aciklama: 'Satılan ürünün depoda ortalama bekleme süresi (gün)', olcu: 'stock_age', yon: 'SATIS_NET', tip: 'num' },
]

export const BOYUTLAR: Blok[] = [
  { id: 'ay', tur: 'boyut', ad: 'Aylara göre', aciklama: 'Zaman içinde ay ay', boyut: 'month', zaman: true },
  { id: 'hafta', tur: 'boyut', ad: 'Haftalara göre', aciklama: 'Zaman içinde hafta hafta', boyut: 'week', zaman: true },
  { id: 'ceyrek', tur: 'boyut', ad: 'Çeyreklere göre', aciklama: 'Üç aylık dönemler', boyut: 'quarter', zaman: true },
  { id: 'yil', tur: 'boyut', ad: 'Yıllara göre', aciklama: 'Yıl yıl', boyut: 'year', zaman: true },
  { id: 'musteri', tur: 'boyut', ad: 'Müşteri', aciklama: 'Müşterilere göre', boyut: 'client' },
  { id: 'grup', tur: 'boyut', ad: 'Firma grubu', aciklama: 'Bağlı firmalar birlikte', boyut: 'client_group' },
  { id: 'urun', tur: 'boyut', ad: 'Ürün', aciklama: 'Ürünlere göre', boyut: 'item' },
  { id: 'marka', tur: 'boyut', ad: 'Marka', aciklama: 'Markalara göre', boyut: 'brand' },
  { id: 'kategori', tur: 'boyut', ad: 'Kategori', aciklama: 'Ürün gruplarına göre', boyut: 'category' },
  { id: 'gelir', tur: 'boyut', ad: 'Gelir tipi', aciklama: 'Ürün ya da tekrarlayan gelir', boyut: 'revenue_type' },
  { id: 'temsilci', tur: 'boyut', ad: 'Temsilci', aciklama: 'Satış temsilcilerine göre', boyut: 'salesman' },
  { id: 'sehir', tur: 'boyut', ad: 'Şehir', aciklama: 'Müşterinin şehri', boyut: 'city' },
  { id: 'gun', tur: 'boyut', ad: 'Haftanın günü', aciklama: 'Pazartesi, salı...', boyut: 'weekday' },
]

export const HAZIRLAR: Blok[] = [
  { id: 'lisanslar', tur: 'hazir', ad: 'Yalnızca lisanslar', aciklama: 'Süreli lisans satışları', filtre: { kind: ['Süreli lisans'] } },
  { id: 'tekrar', tur: 'hazir', ad: 'Tekrarlayan gelir', aciklama: 'Lisans ve abonelikler', filtre: { revenue_type: ['Tekrarlayan'] } },
  { id: 'fiziksel', tur: 'hazir', ad: 'Fiziksel ürün', aciklama: 'Donanım ve diğer ürünler', filtre: { revenue_type: ['Ürün'] } },
]

export const TUM_BLOKLAR = [...OLCULER, ...BOYUTLAR, ...HAZIRLAR]
export const blokBul = (id: string) => TUM_BLOKLAR.find((b) => b.id === id)
export const ZAMAN_BOYUTLARI = new Set(BOYUTLAR.filter((b) => b.zaman).map((b) => b.boyut!))

export const DND_TIPI = 'application/x-tailglass-blok'
