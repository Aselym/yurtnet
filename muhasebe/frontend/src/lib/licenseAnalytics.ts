import type { Sale } from './api'

export const EXPIRING_SOON_DAYS = 90

const INACTIVE_STATUSES: Sale['status'][] = ['EXPIRED', 'NEEDS_DURATION']

export function isExpiringSoon(sale: Sale): boolean {
  return !INACTIVE_STATUSES.includes(sale.status) && sale.days_left >= 0 && sale.days_left <= EXPIRING_SOON_DAYS
}

export function getExpiringSoon(sales: Sale[]): Sale[] {
  return sales.filter(isExpiringSoon).sort((a, b) => a.days_left - b.days_left)
}

export const STATUS_ORDER: Sale['status'][] = [
  'PENDING',
  'FIRST_REMINDER_SENT',
  'FINAL_REMINDER_SENT',
  'EXPIRED',
  'NEEDS_DURATION',
  'RENEWED',
]

export const STATUS_LABELS: Record<Sale['status'], string> = {
  PENDING: 'Beklemede',
  FIRST_REMINDER_SENT: 'İlk Hatırlatma',
  FINAL_REMINDER_SENT: 'Son Hatırlatma',
  EXPIRED: 'Süresi Doldu',
  NEEDS_DURATION: 'Süre Girilmeli',
  RENEWED: 'Yenilendi',
}

// Dataviz skill reference categorical palette (validated, fixed order) — slots 1-6.
export const STATUS_COLORS: Record<Sale['status'], string> = {
  PENDING: '#2a78d6', // blue
  FIRST_REMINDER_SENT: '#eb6834', // orange
  FINAL_REMINDER_SENT: '#1baf7a', // aqua
  EXPIRED: '#eda100', // yellow
  NEEDS_DURATION: '#e87ba4', // magenta
  RENEWED: '#008300', // green
}

export interface StatusCount {
  status: Sale['status']
  label: string
  color: string
  count: number
}

export function getStatusCounts(sales: Sale[]): StatusCount[] {
  const counts = new Map<string, number>()
  for (const s of sales) counts.set(s.status, (counts.get(s.status) ?? 0) + 1)
  return STATUS_ORDER.map((status) => ({
    status,
    label: STATUS_LABELS[status],
    color: STATUS_COLORS[status],
    count: counts.get(status) ?? 0,
  }))
}

export interface MonthlyExpiryBucket {
  key: string // '2026-08'
  label: string // 'Ağu 26'
  count: number
}

const MONTH_LABELS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']

export function getMonthlyExpiryBuckets(sales: Sale[], months = 6): MonthlyExpiryBucket[] {
  const now = new Date()
  const buckets: MonthlyExpiryBucket[] = []
  for (let i = 0; i < months; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    buckets.push({ key, label: `${MONTH_LABELS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`, count: 0 })
  }
  const byKey = new Map(buckets.map((b) => [b.key, b]))

  for (const s of sales) {
    if (INACTIVE_STATUSES.includes(s.status)) continue
    const key = s.expiration_date.slice(0, 7)
    const bucket = byKey.get(key)
    if (bucket) bucket.count += 1
  }

  return buckets
}
