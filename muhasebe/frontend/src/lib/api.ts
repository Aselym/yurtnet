export interface StatsResponse {
  total_sales: number
  active_licenses: number
  expiring_soon: number
  reminders_sent: number
  expired_licenses: number
}

export interface Sale {
  id: number
  product_name: string
  client_name: string
  client_email: string
  sales_rep: string | null
  license_key: string | null
  sale_date: string
  duration_type: string
  duration_months: number
  expiration_date: string
  reminder_type: string
  status: 'PENDING' | 'FIRST_REMINDER_SENT' | 'FINAL_REMINDER_SENT' | 'EXPIRED' | 'NEEDS_DURATION' | 'RENEWED'
  notes: string | null
  days_left: number
  created_at: string
}

export interface Subscription {
  id: number
  client_name: string
  client_email: string | null
  product_name: string
  first_invoice_date: string
  last_invoice_date: string
  invoice_count: number
  avg_interval_days: number | null
  days_since_last: number | null
  status: 'ACTIVE' | 'AT_RISK' | 'LOST'
  source: string | null
  updated_at: string
}

export interface Product {
  id: number
  product_name: string
  product_code: string | null
  client_name: string
  client_email: string | null
  quantity: number
  unit_price: number | null
  line_total: number | null
  currency: string
  sale_date: string
  invoice_no: string | null
  source: string | null
  created_at: string
}

async function getJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(path, { credentials: 'include' })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

export function getStats(): Promise<StatsResponse | null> {
  return getJson<StatsResponse>('/api/stats')
}

export function getSales(): Promise<Sale[] | null> {
  return getJson<Sale[]>('/api/sales')
}

export function getSubscriptions(): Promise<Subscription[] | null> {
  return getJson<Subscription[]>('/api/subscriptions')
}

export function getProducts(): Promise<Product[] | null> {
  return getJson<Product[]>('/api/products')
}
