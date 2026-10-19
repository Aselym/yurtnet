// Tek API istemcisi. Oturum cerezle tasinir (credentials: 'include').

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && !path.includes('/login') && !path.includes('check-auth')) {
    onUnauthorized?.()
  }
  const text = await res.text()
  let data: unknown = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!res.ok) {
    const msg = (data as { message?: string; error?: string } | null)?.message ||
      (data as { error?: string } | null)?.error || `İstek başarısız (${res.status})`
    throw new ApiError(res.status, msg)
  }
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}

/** Excel gibi dosya donen POST uclari: tarayiciya indirme baslatir. */
export async function download(path: string, body: unknown, fallbackName = 'rapor.xlsx') {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    let msg = `İndirme başarısız (${res.status})`
    try {
      msg = (await res.json()).message || msg
    } catch { /* yok say */ }
    throw new ApiError(res.status, msg)
  }
  const cd = res.headers.get('Content-Disposition') || ''
  const m = /filename\*=UTF-8''([^;]+)/.exec(cd) || /filename="([^"]+)"/.exec(cd)
  const name = m ? decodeURIComponent(m[1]) : fallbackName
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

// ------------------------------------------------------------------ tipler
export type Direction = 'SATIS_NET' | 'SATIS' | 'ALIS_NET' | 'ALIS' | 'TUMU'
export type FilterValue = string[] | { not: boolean; values: string[] }
export type Filters = Record<string, FilterValue>

export interface Dimension { key: string; label: string; filterable: boolean }
export interface Measure { key: string; label: string; type: ColType }
export type ColType = 'tl' | 'usd' | 'num' | 'pct' | 'date' | 'text' | 'dim'

export interface Meta {
  dimensions: Dimension[]
  measures: Measure[]
  directions: { key: Direction; label: string }[]
  data: { first: string | null; last: string | null; lines: number; last_sync: SyncLog | null }
  settings: Record<string, string | null>
}

export interface SyncLog {
  id: number; started_at: string; finished_at: string; source: string; ok: number
  lines: number; items: number; clients: number; message: string
}

export interface QueryRequest {
  date_from?: string; date_to?: string; direction?: Direction; filters?: Filters; search?: string
  group_by?: string[]; pivot_by?: string | null; measures?: string[]; sort?: { key: string; desc?: boolean }
  limit?: number; offset?: number; pivot_limit?: number
}

export interface Column { key: string; label: string; type: ColType; dim?: string; measure?: string; pivot?: string }
export interface QueryResult {
  columns: Column[]
  rows: Record<string, unknown>[]
  totals: Record<string, number | null>
  row_count: number
  pivot?: { by: string; measure: string; values: string[] }
}

export interface LinesResult { columns: Column[]; rows: Record<string, unknown>[]; total: number; offset: number; limit: number }

export interface Sale {
  id: number; product_name: string; client_name: string; client_email: string; sales_rep: string | null
  license_key: string | null; sale_date: string; duration_type: string; duration_months: number
  expiration_date: string; status: string; notes: string | null; days_left: number
  renewal_state: 'SUSPECT' | 'CONFIRMED' | 'REJECTED' | null; renewed_by: number | null; price: number | null
  client_phone: string | null; client_city: string | null; reminders_sent_count?: number
}

export interface Subscription {
  id: number; client_name: string; client_email: string | null; product_name: string
  first_invoice_date: string; last_invoice_date: string; invoice_count: number
  avg_interval_days: number | null; days_since_last: number | null; status: 'ACTIVE' | 'AT_RISK' | 'LOST'
  client_phone: string | null; client_city: string | null
}

export interface Offer {
  id: number; product_name: string; quantity: number; client_name: string; offer_price: number | null
  currency: string; offer_date: string; sales_rep: string | null; status: 'PENDING' | 'ACCEPTED' | 'REJECTED'
  notes: string | null
}

export interface ActionResult { success: boolean; message: string; [k: string]: unknown }
