import type { Direction, QueryResult } from '../../lib/api'
import { iso, today } from '../../lib/state'
import { OLCULER, blokBul } from './bloklar'

export type Grafik = 'otomatik' | 'cubuk' | 'cizgi' | 'tablo' | 'sayi'
export interface Aralik { tur: 'pano' | 'ozel'; from: string; to: string }

/** Izgaradaki bir kart: bir olcu, istege bagli bir kirilim, kendi araligi ve filtreleri. */
export interface Kart {
  id: string
  olcu: string                     // OLCULER blok id
  boyut?: string                   // analiz motoru boyut anahtari
  seri?: string                    // ikinci kirilim (renklere bol)
  filtre: Record<string, string[]> // boyut -> secili degerler
  aralik: Aralik
  ust: number                      // kategori kirilimlarinda ilk N
  grafik: Grafik
  genis: 1 | 2
  not: string
}

export interface Pano {
  ad: string
  aralik: { from: string; to: string }
  hucreler: (Kart | null)[]
  not: string
}

export const yeniId = () => Math.random().toString(36).slice(2, 9)

export function varsayilanPano(): Pano {
  const t = new Date()
  return {
    ad: 'Yeni analiz',
    aralik: { from: iso(new Date(t.getFullYear() - 1, t.getMonth() + 1, 1)), to: today() },
    hucreler: Array(6).fill(null),
    not: '',
  }
}

export function yeniKart(olcu = 'satis'): Kart {
  return { id: yeniId(), olcu, filtre: {}, aralik: { tur: 'pano', from: '', to: '' }, ust: 10, grafik: 'otomatik', genis: 1, not: '' }
}

export const kartAraligi = (k: Kart, p: Pano) => (k.aralik.tur === 'pano' ? p.aralik : { from: k.aralik.from, to: k.aralik.to })

export function olcuBlok(k: Kart) {
  return blokBul(k.olcu) ?? OLCULER[0]
}

/** Kartin analiz motoru istegi. */
export function istek(k: Kart, p: Pano, onceki = false) {
  const b = olcuBlok(k)
  let { from, to } = kartAraligi(k, p)
  if (onceki) [from, to] = oncekiDonem(from, to)
  const group_by = [k.boyut, k.seri].filter(Boolean) as string[]
  return {
    date_from: from, date_to: to, direction: b.yon as Direction, measures: [b.olcu!],
    group_by, filters: k.filtre, sort: { key: `m_${b.olcu}`, desc: true }, limit: 0,
  }
}

/** Ayni uzunluktaki bir onceki donem. */
export function oncekiDonem(from: string, to: string): [string, string] {
  const f = new Date(from), t = new Date(to)
  const gun = Math.round((t.getTime() - f.getTime()) / 86400000) + 1
  const pt = new Date(f.getTime() - 86400000)
  const pf = new Date(pt.getTime() - (gun - 1) * 86400000)
  return [iso(pf), iso(pt)]
}

export interface KartVeri { sonuc: QueryResult; onceki?: QueryResult; surucu?: { donem: string; satirlar: { ad: string; deger: number }[]; toplam: number } }

/** Kartin otomatik basligi: "Aylara göre satış · Dell, HP". */
export function kartBasligi(k: Kart, etiket: (dim: string) => string) {
  const b = olcuBlok(k)
  let t = b.ad
  if (k.boyut) t = `${etiket(k.boyut)} bazında ${b.ad.toLocaleLowerCase('tr')}`
  if (k.seri) t += `, ${etiket(k.seri).toLocaleLowerCase('tr')} kırılımıyla`
  return t
}

/** Zaman kiriliminin bir dilimini tarih araligina cevirir (zirve donemi incelemesi icin). */
export function dilimAraligi(key: string, gran: string): [string, string] | null {
  if (gran === 'month' && /^\d{4}-\d{2}$/.test(key)) {
    const [y, m] = key.split('-').map(Number)
    return [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))]
  }
  if (gran === 'year' && /^\d{4}$/.test(key)) return [`${key}-01-01`, `${key}-12-31`]
  if (gran === 'day') return [key, key]
  if (gran === 'quarter' && key.includes('-Ç')) {
    const [y, q] = key.split('-Ç').map(Number)
    return [iso(new Date(y, (q - 1) * 3, 1)), iso(new Date(y, q * 3, 0))]
  }
  return null
}
