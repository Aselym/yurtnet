import type { ColType } from './api'

const tl0 = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 })
const tl2 = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const num = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2 })
const pct = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })

export function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

/** Tablo hucresi icin tam deger. */
export function fmt(v: unknown, type: ColType, opts: { decimals?: boolean } = {}): string {
  if (v === null || v === undefined || v === '') return '—'
  if (!isNum(v)) {
    if (type === 'date' && typeof v === 'string') return fmtDate(v)
    return String(v)
  }
  switch (type) {
    case 'tl': return `${(opts.decimals ? tl2 : tl0).format(v)} ₺`
    case 'usd': return `$${(opts.decimals ? tl2 : tl0).format(v)}`
    case 'pct': return `%${pct.format(v)}`
    case 'num': return num.format(v)
    default: return String(v)
  }
}

/** Dar alanlar (stat, eksen) icin kisaltilmis deger: 1,87 Mn ₺ */
export function fmtShort(v: unknown, type: ColType = 'num'): string {
  if (!isNum(v)) return '—'
  const abs = Math.abs(v)
  let s: string
  if (abs >= 1e9) s = `${num.format(v / 1e9)} Mr`
  else if (abs >= 1e6) s = `${num.format(Math.round(v / 1e4) / 100)} Mn`
  else if (abs >= 1e4) s = `${num.format(Math.round(v / 100) / 10)} B`
  else s = tl0.format(v)
  if (type === 'tl') return `${s} ₺`
  if (type === 'usd') return `$${s}`
  if (type === 'pct') return `%${pct.format(v)}`
  return s
}

const AYLAR = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']
const AYLAR_UZUN = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim',
  'Kasım', 'Aralık']

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  if (!d) return iso
  return `${d}.${m}.${y}`
}

export function fmtDateLong(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return `${d} ${AYLAR_UZUN[m - 1]} ${y}`
}

/** Analiz motorundan gelen zaman anahtarlarini okunur yapar: 2026-03 -> Mar 26 */
export function fmtPeriodKey(key: unknown, dim?: string): string {
  if (typeof key !== 'string') return key == null ? '—' : String(key)
  if (dim === 'month' || /^\d{4}-\d{2}$/.test(key)) {
    const [y, m] = key.split('-')
    return `${AYLAR[Number(m) - 1]} ${y.slice(2)}`
  }
  if (dim === 'day' || /^\d{4}-\d{2}-\d{2}$/.test(key)) {
    const [, m, d] = key.split('-')
    return `${Number(d)} ${AYLAR[Number(m) - 1]}`
  }
  if (dim === 'weekday') return key.replace(/^\d\s/, '')
  return key
}

export function rangeLabel(from: string, to: string): string {
  const [fy, fm, fd] = from.split('-').map(Number)
  const [ty, tm, td] = to.split('-').map(Number)
  const ayinSonu = new Date(ty, tm, 0).getDate()
  if (fd === 1 && td === ayinSonu) {
    if (fy === ty && fm === tm) return `${AYLAR_UZUN[fm - 1]} ${fy}`
    if (fm === 1 && tm === 12) return fy === ty ? `${fy}` : `${fy} – ${ty}`
    return `${AYLAR[fm - 1]} ${fy} – ${AYLAR[tm - 1]} ${ty}`
  }
  return `${fmtDate(from)} – ${fmtDate(to)}`
}

export function delta(cur: number | null | undefined, prev: number | null | undefined): number | null {
  if (!isNum(cur) || !isNum(prev) || prev === 0) return null
  return ((cur - prev) / Math.abs(prev)) * 100
}

export const DIRECTION_LABEL: Record<string, string> = {
  SATIS: 'Satış', ALIS: 'Alış', SATIS_IADE: 'Satış iadesi', ALIS_IADE: 'Alış iadesi',
}
