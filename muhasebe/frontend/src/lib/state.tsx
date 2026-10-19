import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, type Filters, type FilterValue, type Meta } from './api'

// Global calisma durumu: secili donem + filtreler + para birimi.
// Butun sayfalar ayni durumu paylasir (kullanici Genel bakis'ta Dell'i
// secip Satislar'a gectiginde Dell secili kalir) ve tarayicida hatirlanir.

export type Currency = 'TL' | 'USD' | 'BOTH'
export type Compare = 'previous' | 'year' | 'none'

export interface WorkState {
  from: string
  to: string
  filters: Filters
  currency: Currency
  compare: Compare
}

interface Ctx extends WorkState {
  meta: Meta | null
  reloadMeta: () => Promise<void>
  setPeriod: (from: string, to: string) => void
  setFilter: (dim: string, value: FilterValue | null) => void
  clearFilters: () => void
  setCurrency: (c: Currency) => void
  setCompare: (c: Compare) => void
  /** analiz istegi icin ortak parcalar */
  base: { date_from: string; date_to: string; filters: Filters }
}

const StateContext = createContext<Ctx | null>(null)
const KEY = 'defter.calisma'

export function iso(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function today(): string {
  return iso(new Date())
}

function load(): WorkState {
  const d = new Date()
  const fallback: WorkState = {
    from: iso(new Date(d.getFullYear() - 1, d.getMonth(), d.getDate() + 1)),
    to: iso(d),
    filters: {},
    currency: 'TL',
    compare: 'previous',
  }
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return fallback
    return { ...fallback, ...JSON.parse(raw) }
  } catch {
    return fallback
  }
}

export function StateProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<WorkState>(load)
  const [meta, setMeta] = useState<Meta | null>(null)

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(s))
    } catch { /* gizli pencere vb. */ }
  }, [s])

  const reloadMeta = useCallback(async () => {
    try {
      setMeta(await api.get<Meta>('/api/meta'))
    } catch { /* oturum yoksa App ilgilenir */ }
  }, [])

  useEffect(() => {
    reloadMeta()
  }, [reloadMeta])

  // Urun adi sabit; sekme basliginda lisans sahibi sirket de gorunur
  useEffect(() => {
    const sirket = meta?.settings?.company_name
    document.title = sirket ? `Tailglass Analytics — ${sirket}` : 'Tailglass Analytics'
  }, [meta])

  const value = useMemo<Ctx>(() => ({
    ...s,
    meta,
    reloadMeta,
    setPeriod: (from, to) => setS((p) => ({ ...p, from: from <= to ? from : to, to: from <= to ? to : from })),
    setFilter: (dim, v) => setS((p) => {
      const f = { ...p.filters }
      const bos = !v || (Array.isArray(v) ? v.length === 0 : v.values.length === 0)
      if (bos) delete f[dim]
      else f[dim] = v
      return { ...p, filters: f }
    }),
    clearFilters: () => setS((p) => ({ ...p, filters: {} })),
    setCurrency: (currency) => setS((p) => ({ ...p, currency })),
    setCompare: (compare) => setS((p) => ({ ...p, compare })),
    base: { date_from: s.from, date_to: s.to, filters: s.filters },
  }), [s, meta, reloadMeta])

  return <StateContext.Provider value={value}>{children}</StateContext.Provider>
}

export function useWork(): Ctx {
  const c = useContext(StateContext)
  if (!c) throw new Error('StateProvider yok')
  return c
}

export function filterValues(v: FilterValue | undefined): string[] {
  if (!v) return []
  return Array.isArray(v) ? v : v.values
}

export function isExclude(v: FilterValue | undefined): boolean {
  return !!v && !Array.isArray(v) && v.not
}

/** Para birimi tercihine gore gosterilecek tutar olculeri */
export function moneyMeasures(c: Currency, tl = 'net_tl', usd = 'net_usd'): string[] {
  return c === 'TL' ? [tl] : c === 'USD' ? [usd] : [tl, usd]
}
