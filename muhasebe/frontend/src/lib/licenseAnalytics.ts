import type { Sale } from './api'

export const EXPIRING_SOON_DAYS = 90

const INACTIVE_STATUSES: Sale['status'][] = ['EXPIRED', 'NEEDS_DURATION']

export function isExpiringSoon(sale: Sale): boolean {
  return !INACTIVE_STATUSES.includes(sale.status) && sale.days_left >= 0 && sale.days_left <= EXPIRING_SOON_DAYS
}

// Lisanslar listesini kalabalıklaştıran, çoktan 2024'te süresi dolmuş kayıtlar.
// Logo'dan otomatik senkron her gün tekrar çektiği için veritabanından
// silinmiyor, sadece varsayılan görünümden gizleniyor.
export function isStaleExpired(sale: Sale): boolean {
  return sale.status === 'EXPIRED' && sale.expiration_date.startsWith('2024')
}

// Süresi dolmuş ve otomatik yenileme eşleştiricisinin (yenileme_adaylari_bul)
// ya hiç aday bulamadığı ya da satış ekibinin yanlış eşleşme dediği kayıtlar.
export function isLostCustomer(sale: Sale): boolean {
  return sale.status === 'EXPIRED' && (sale.renewal_state === null || sale.renewal_state === 'REJECTED')
}

export function getLostCustomers(sales: Sale[]): Sale[] {
  return sales.filter(isLostCustomer).sort((a, b) => a.expiration_date.localeCompare(b.expiration_date))
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

export const MONTH_LABELS = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara']

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

export interface RevenueForecastBucket {
  key: string
  label: string
  revenue: number
  missingPrice: number
}

export function getRevenueForecast(sales: Sale[], months = 3): RevenueForecastBucket[] {
  const now = new Date()
  const buckets: RevenueForecastBucket[] = []
  for (let i = 0; i < months; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() + i, 1)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    buckets.push({ key, label: `${MONTH_LABELS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`, revenue: 0, missingPrice: 0 })
  }
  const byKey = new Map(buckets.map((b) => [b.key, b]))

  for (const s of sales) {
    if (INACTIVE_STATUSES.includes(s.status)) continue
    const key = s.expiration_date.slice(0, 7)
    const bucket = byKey.get(key)
    if (!bucket) continue
    if (s.price) bucket.revenue += s.price
    else bucket.missingPrice += 1
  }

  return buckets
}

// logo_sync.py'deki LISANS_MARKALARI ile aynı marka gruplaması (yazım hatalı
// varyantlar dahil) — kanonik marka adına katlanmış hali.
const BRAND_PATTERNS: { label: string; keywords: string[] }[] = [
  { label: 'WatchGuard', keywords: ['WATCHGUARD', 'WATCGUARD', 'WATCGHUARD'] },
  { label: 'FortiGate', keywords: ['FORTIGATE', 'FOTIGATE', 'FORTINET'] },
  { label: 'Veeam', keywords: ['VEEAM'] },
  { label: '5651 / Loglama', keywords: ['PLOG', '5651', 'SIGNLOGGER', 'CRYPTTECH'] },
  { label: 'Sophos', keywords: ['SOPHOS'] },
  { label: 'ESET', keywords: ['ESET'] },
  { label: 'Kaspersky', keywords: ['KASPERSKY'] },
  { label: 'Bitdefender', keywords: ['BITDEFENDER'] },
  { label: 'Trellix', keywords: ['TRELLIX'] },
  { label: 'Adobe', keywords: ['ADOBE'] },
  { label: 'AutoCAD / Autodesk', keywords: ['AUTOCAD', 'AUTODESK'] },
  { label: 'VMware', keywords: ['VMWARE'] },
]

function brandOf(productName: string): string | null {
  const upper = productName.toUpperCase()
  for (const { label, keywords } of BRAND_PATTERNS) {
    if (keywords.some((k) => upper.includes(k))) return label
  }
  return null
}

export interface BrandStats {
  brand: string
  active: number
  expired: number
  renewed: number
  renewalRate: number | null // yüzde, 0-100
}

export function getBrandStats(sales: Sale[]): BrandStats[] {
  const byBrand = new Map<string, BrandStats>()

  for (const s of sales) {
    const brand = brandOf(s.product_name)
    if (!brand) continue
    let stats = byBrand.get(brand)
    if (!stats) {
      stats = { brand, active: 0, expired: 0, renewed: 0, renewalRate: null }
      byBrand.set(brand, stats)
    }
    if (s.status === 'EXPIRED') {
      stats.expired += 1
      if (s.renewal_state === 'CONFIRMED') stats.renewed += 1
    } else if (s.status !== 'NEEDS_DURATION') {
      stats.active += 1
    }
  }

  for (const stats of byBrand.values()) {
    stats.renewalRate = stats.expired > 0 ? Math.round((stats.renewed / stats.expired) * 100) : null
  }

  return [...byBrand.values()]
    .filter((s) => s.active + s.expired > 0)
    .sort((a, b) => b.active + b.expired - (a.active + a.expired))
}
