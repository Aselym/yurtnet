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

/** Dar alanlar (eksen, liste) icin kisaltilmis deger — kurus/ondalik YOK:
 *  1.531.277.730 -> "1 milyar 531 milyon", 697.670.000 -> "698 milyon", 45.300 -> "45 bin" */
export function fmtShort(v: unknown, type: ColType = 'num'): string {
  if (!isNum(v)) return '—'
  if (type === 'pct') return `%${pct.format(v)}`
  const s = kisaOkunus(v)
  if (type === 'tl') return `${s} ₺`
  if (type === 'usd') return `$${s}`
  return s
}

function kisaOkunus(v: number): string {
  const isaret = v < 0 ? '-' : ''
  const a = Math.abs(v)
  if (a >= 1e9) {
    const mr = Math.floor(a / 1e9)
    const mn = Math.round((a - mr * 1e9) / 1e6)
    return `${isaret}${tl0.format(mr)} milyar${mn ? ` ${mn} milyon` : ''}`
  }
  if (a >= 1e8) return `${isaret}${Math.round(a / 1e6)} milyon`
  if (a >= 1e6) {
    const mn = Math.floor(a / 1e6)
    const bin = Math.round((a - mn * 1e6) / 1e3)
    return `${isaret}${mn} milyon${bin ? ` ${bin} bin` : ''}`
  }
  if (a >= 1e4) return `${isaret}${Math.round(a / 1e3)} bin`
  return `${isaret}${tl0.format(Math.round(a))}`
}

/** Grafik ekseni: ondaliksiz, kisa ("250 bin", "1.500 milyon") */
export function fmtAxis(v: number, type: ColType = 'num'): string {
  const a = Math.abs(v)
  let s: string
  if (type === 'pct') return `%${Math.round(v)}`
  if (a >= 1e6) s = `${tl0.format(Math.round(v / 1e6))} milyon`
  else if (a >= 1e4) s = `${tl0.format(Math.round(v / 1e3))} bin`
  else s = tl0.format(Math.round(v))
  return type === 'usd' ? `$${s}` : type === 'tl' ? `${s} ₺` : s
}

/** Eksen icin yuvarlak adimlar: 1, 2, 5 x 10^k */
export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1]
  const kaba = max / count
  const us = Math.pow(10, Math.floor(Math.log10(kaba)))
  const adim = [1, 2, 2.5, 5, 10].map((k) => k * us).find((x) => x >= kaba) ?? 10 * us
  const out: number[] = []
  for (let v = 0; v <= max + adim * 0.999; v += adim) out.push(v)
  return out
}

/** Buyuk rakamin altina yazilan Turkce okunus: 761.051.421 -> "761 milyon 51 bin lira" */
export function fmtSpoken(v: unknown, type: ColType = 'tl'): string | null {
  if (!isNum(v) || Math.abs(v) < 10000) return null
  const a = Math.abs(v)
  const parca: string[] = []
  let kalan = Math.round(a)
  const mr = Math.floor(kalan / 1e9); kalan -= mr * 1e9
  const mn = Math.floor(kalan / 1e6); kalan -= mn * 1e6
  const bin = Math.floor(kalan / 1e3); kalan -= bin * 1e3
  if (mr) parca.push(`${tl0.format(mr)} milyar`)
  if (mn) parca.push(`${mn} milyon`)
  if (bin) parca.push(`${bin} bin`)
  if (!mr && !mn && kalan) parca.push(String(kalan))   // milyonun altinda yuzler de okunur
  const birim = type === 'usd' ? 'dolar' : type === 'tl' ? 'lira' : ''
  return `${v < 0 ? 'eksi ' : ''}${parca.join(' ')}${birim ? ` ${birim}` : ''}`
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
