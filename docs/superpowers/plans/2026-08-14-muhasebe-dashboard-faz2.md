# Muhasebe Dashboard (Faz 2 — Alt-proje 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `"satis"` role's `PlaceholderPanel` with a real sidebar-layout Dashboard (Özet/Lisanslar/Abonelikler/Ürünler tabs + a "Teklifler" coming-soon stub), reading from the existing, unmodified backend.

**Architecture:** New `DashboardPage` owns a `DashboardTab` state (`overview | licenses | subscriptions | products | offers`) and renders a fixed `Sidebar` plus the active tab's content. Each data tab (`OverviewTab`, `LicensesTab`, `SubscriptionsTab`, `ProductsTab`) independently fetches its own endpoint via `lib/api.ts` and renders through a shared `DataTable` shell. `App.tsx` swaps which panel it renders based on `role`: `'satis'` → `DashboardPage`, `'yonetici'` → unchanged `PlaceholderPanel`. No client-side router (unchanged from Faz 1) — the backend still only whitelists `/`, `/login`, `/dashboard`.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, `lucide-react` icons, existing `@/components/ui/*` primitives (`Button`, `Card`, `Input`) and `@/lib/cn`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-14-muhasebe-dashboard-faz2-design.md`

## Global Constraints

- Backend (`muhasebe/app.py`) is NOT modified — only the existing `GET /api/stats`, `GET /api/sales`, `GET /api/subscriptions`, `GET /api/products` endpoints are consumed, exactly as they respond today.
- No automated test framework this phase (matches Faz 1's documented decision). Verification is `npm run build` per task, plus a final manual QA pass via Browser preview.
- Every fetch call uses `credentials: 'include'` and the fail-safe pattern from `lib/auth.ts`: catch errors, return `null` on failure — never throw past the call site.
- Reuse Faz 1's brand tokens (`bg-brand`, `text-brand`, `bg-brand-soft`, etc.) and dark-mode variant (`dark:` driven by `data-theme="dark"`) — no new design tokens.
- `DashboardPage` is rendered only after `App.tsx` has already confirmed auth and role (Faz 1's `checkAuth` + `sessionStorage` gate) — no additional auth check is added inside the dashboard.
- Scope excludes (per spec, not silently dropped): the "Müşteriye Mail Gönder" action, `NEEDS_DURATION` duration-entry, and renewal-candidate approve/reject actions. The "Teklifler" tab is a stub in this plan only.

---

### Task 1: API client for dashboard data

**Files:**
- Create: `muhasebe/frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  - `interface StatsResponse { total_sales: number; active_licenses: number; expiring_soon: number; reminders_sent: number; expired_licenses: number }`
  - `interface Sale { id: number; product_name: string; client_name: string; client_email: string; sales_rep: string | null; license_key: string | null; sale_date: string; duration_type: string; duration_months: number; expiration_date: string; reminder_type: string; status: 'PENDING' | 'FIRST_REMINDER_SENT' | 'FINAL_REMINDER_SENT' | 'EXPIRED' | 'NEEDS_DURATION' | 'RENEWED'; notes: string | null; days_left: number; created_at: string }`
  - `interface Subscription { id: number; client_name: string; client_email: string | null; product_name: string; first_invoice_date: string; last_invoice_date: string; invoice_count: number; avg_interval_days: number | null; days_since_last: number | null; status: 'ACTIVE' | 'AT_RISK' | 'LOST'; source: string | null; updated_at: string }`
  - `interface Product { id: number; product_name: string; product_code: string | null; client_name: string; client_email: string | null; quantity: number; unit_price: number | null; line_total: number | null; currency: string; sale_date: string; invoice_no: string | null; source: string | null; created_at: string }`
  - `getStats(): Promise<StatsResponse | null>`
  - `getSales(): Promise<Sale[] | null>`
  - `getSubscriptions(): Promise<Subscription[] | null>`
  - `getProducts(): Promise<Product[] | null>`

- [ ] **Step 1: Create `src/lib/api.ts`**

```ts
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
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0 (nothing imports this file yet, so this only checks for TypeScript syntax errors).

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/lib/api.ts
git commit -m "feat(muhasebe-frontend): add dashboard API client (stats/sales/subscriptions/products)"
```

---

### Task 2: StatusPill component

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/StatusPill.tsx`

**Interfaces:**
- Consumes: `cn` from `@/lib/cn` (Faz 1, Task 3).
- Produces: `<StatusPill status={string} />` — renders any status string; unknown statuses fall back to a neutral style showing the raw value.

- [ ] **Step 1: Create `src/components/dashboard/StatusPill.tsx`**

```tsx
import { cn } from '@/lib/cn'

const STATUS_STYLES: Record<string, string> = {
  PENDING: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
  FIRST_REMINDER_SENT: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  FINAL_REMINDER_SENT: 'bg-orange-50 text-orange-600 dark:bg-orange-500/10 dark:text-orange-400',
  EXPIRED: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
  NEEDS_DURATION: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-white/60',
  RENEWED: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  ACTIVE: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  AT_RISK: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  LOST: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
}

const STATUS_LABELS: Record<string, string> = {
  PENDING: 'Beklemede',
  FIRST_REMINDER_SENT: 'İlk Hatırlatma Gönderildi',
  FINAL_REMINDER_SENT: 'Son Hatırlatma Gönderildi',
  EXPIRED: 'Süresi Doldu',
  NEEDS_DURATION: 'Süre Girilmeli',
  RENEWED: 'Yenilendi',
  ACTIVE: 'Aktif',
  AT_RISK: 'Riskli',
  LOST: 'Kayıp',
}

interface StatusPillProps {
  status: string
}

export function StatusPill({ status }: StatusPillProps) {
  const style = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-white/60'
  const label = STATUS_LABELS[status] ?? status

  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', style)}>
      {label}
    </span>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/StatusPill.tsx
git commit -m "feat(muhasebe-frontend): add StatusPill for license/subscription status badges"
```

---

### Task 3: StatCard component

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/StatCard.tsx`

**Interfaces:**
- Consumes: `Card` from `@/components/ui/card` (Faz 1, Task 3); `LucideIcon` type from `lucide-react`.
- Produces: `<StatCard label={string} value={number} icon={LucideIcon} tone?={'default'|'warn'|'danger'} />`

- [ ] **Step 1: Create `src/components/dashboard/StatCard.tsx`**

```tsx
import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/cn'

interface StatCardProps {
  label: string
  value: number
  icon: LucideIcon
  tone?: 'default' | 'warn' | 'danger'
}

const TONE_STYLES: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'text-brand bg-brand-soft dark:bg-brand/10',
  warn: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10',
  danger: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10',
}

export function StatCard({ label, value, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div className={cn('flex h-12 w-12 shrink-0 items-center justify-center rounded-xl', TONE_STYLES[tone])}>
        <Icon className="h-6 w-6" strokeWidth={1.75} />
      </div>
      <div>
        <p className="text-2xl font-semibold text-black/90 dark:text-white">{value}</p>
        <p className="text-sm text-black/50 dark:text-white/50">{label}</p>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/StatCard.tsx
git commit -m "feat(muhasebe-frontend): add StatCard KPI card"
```

---

### Task 4: DataTable component

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/DataTable.tsx`

**Interfaces:**
- Consumes: `Card`, `Input`, `Button` from `@/components/ui/*` (Faz 1, Task 3).
- Produces:
  - `interface DataTableColumn<T> { key: string; header: string; render: (row: T) => React.ReactNode }`
  - `<DataTable columns={DataTableColumn<T>[]} rows={T[]} status={'loading'|'error'|'ready'} onRetry={() => void} searchPlaceholder={string} searchValue={string} onSearchChange={(v: string) => void} getRowKey={(row: T) => string | number} emptyMessage={string} />` — generic over `T`, used identically by Tasks 5-7.

- [ ] **Step 1: Create `src/components/dashboard/DataTable.tsx`**

```tsx
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

export interface DataTableColumn<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  status: 'loading' | 'error' | 'ready'
  onRetry: () => void
  searchPlaceholder: string
  searchValue: string
  onSearchChange: (value: string) => void
  getRowKey: (row: T) => string | number
  emptyMessage: string
}

export function DataTable<T>({
  columns,
  rows,
  status,
  onRetry,
  searchPlaceholder,
  searchValue,
  onSearchChange,
  getRowKey,
  emptyMessage,
}: DataTableProps<T>) {
  return (
    <div className="space-y-4">
      <Input
        value={searchValue}
        onChange={(e) => onSearchChange(e.target.value)}
        placeholder={searchPlaceholder}
        className="max-w-xs"
      />
      <Card className="overflow-x-auto p-0">
        {status === 'loading' && (
          <div className="space-y-2 p-5">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-lg bg-black/5 dark:bg-white/5" />
            ))}
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 p-10 text-center">
            <p className="text-sm text-black/50 dark:text-white/50">Veriler yüklenemedi.</p>
            <Button variant="ghost" onClick={onRetry}>
              Tekrar dene
            </Button>
          </div>
        )}

        {status === 'ready' && rows.length === 0 && (
          <p className="p-10 text-center text-sm text-black/50 dark:text-white/50">{emptyMessage}</p>
        )}

        {status === 'ready' && rows.length > 0 && (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/5 text-xs uppercase tracking-wide text-black/40 dark:border-white/10 dark:text-white/40">
                {columns.map((col) => (
                  <th key={col.key} className="px-5 py-3 font-medium">
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={getRowKey(row)} className="border-b border-black/5 last:border-0 dark:border-white/5">
                  {columns.map((col) => (
                    <td key={col.key} className="px-5 py-3 text-black/80 dark:text-white/80">
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/DataTable.tsx
git commit -m "feat(muhasebe-frontend): add generic DataTable shell (search, loading, error, empty states)"
```

---

### Task 5: OverviewTab

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/OverviewTab.tsx`

**Interfaces:**
- Consumes: `getStats`, `StatsResponse` from `@/lib/api` (Task 1); `StatCard` from `./StatCard` (Task 3); `Button` from `@/components/ui/button`.
- Produces: `<OverviewTab />` — no props, self-contained.

- [ ] **Step 1: Create `src/components/dashboard/OverviewTab.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { BadgeCheck, Clock, Mail, Package, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StatCard } from './StatCard'
import { getStats, type StatsResponse } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function OverviewTab() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const data = await getStats()
    if (data) {
      setStats(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (status === 'loading') {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl bg-black/5 dark:bg-white/5" />
        ))}
      </div>
    )
  }

  if (status === 'error' || !stats) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-2xl border border-black/5 p-10 text-center dark:border-white/10">
        <p className="text-sm text-black/50 dark:text-white/50">Veriler yüklenemedi.</p>
        <Button variant="ghost" onClick={load}>
          Tekrar dene
        </Button>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <StatCard label="Toplam Satış" value={stats.total_sales} icon={Package} />
      <StatCard label="Aktif Lisans" value={stats.active_licenses} icon={BadgeCheck} />
      <StatCard label="Yakında Dolacak" value={stats.expiring_soon} icon={Clock} tone="warn" />
      <StatCard label="Gönderilen Hatırlatma" value={stats.reminders_sent} icon={Mail} />
      <StatCard label="Süresi Dolmuş" value={stats.expired_licenses} icon={XCircle} tone="danger" />
    </div>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/OverviewTab.tsx
git commit -m "feat(muhasebe-frontend): add OverviewTab with 5 KPI stat cards"
```

---

### Task 6: LicensesTab

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/LicensesTab.tsx`

**Interfaces:**
- Consumes: `getSales`, `Sale` from `@/lib/api` (Task 1); `DataTable`, `DataTableColumn` from `./DataTable` (Task 4); `StatusPill` from `./StatusPill` (Task 2).
- Produces: `<LicensesTab />` — no props, self-contained.

- [ ] **Step 1: Create `src/components/dashboard/LicensesTab.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { getSales, type Sale } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function LicensesTab() {
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')

  async function load() {
    setStatus('loading')
    const data = await getSales()
    if (data) {
      setSales(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sales
    return sales.filter(
      (s) => s.client_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q)
    )
  }, [sales, search])

  const columns: DataTableColumn<Sale>[] = [
    { key: 'client', header: 'Müşteri', render: (s) => s.client_name },
    { key: 'product', header: 'Ürün', render: (s) => s.product_name },
    { key: 'expiration', header: 'Bitiş Tarihi', render: (s) => s.expiration_date },
    { key: 'days_left', header: 'Kalan Gün', render: (s) => (s.days_left >= 0 ? `${s.days_left} gün` : '-') },
    { key: 'status', header: 'Durum', render: (s) => <StatusPill status={s.status} /> },
  ]

  return (
    <DataTable
      columns={columns}
      rows={filtered}
      status={status}
      onRetry={load}
      searchPlaceholder="Müşteri veya ürün ara..."
      searchValue={search}
      onSearchChange={setSearch}
      getRowKey={(s) => s.id}
      emptyMessage="Henüz lisans kaydı yok."
    />
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/LicensesTab.tsx
git commit -m "feat(muhasebe-frontend): add LicensesTab (sales) with search and status pills"
```

---

### Task 7: SubscriptionsTab

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/SubscriptionsTab.tsx`

**Interfaces:**
- Consumes: `getSubscriptions`, `Subscription` from `@/lib/api` (Task 1); `DataTable`, `DataTableColumn` from `./DataTable` (Task 4); `StatusPill` from `./StatusPill` (Task 2).
- Produces: `<SubscriptionsTab />` — no props, self-contained.

- [ ] **Step 1: Create `src/components/dashboard/SubscriptionsTab.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { getSubscriptions, type Subscription } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function SubscriptionsTab() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')

  async function load() {
    setStatus('loading')
    const data = await getSubscriptions()
    if (data) {
      setSubscriptions(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return subscriptions
    return subscriptions.filter(
      (s) => s.client_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q)
    )
  }, [subscriptions, search])

  const columns: DataTableColumn<Subscription>[] = [
    { key: 'client', header: 'Müşteri', render: (s) => s.client_name },
    { key: 'product', header: 'Ürün', render: (s) => s.product_name },
    { key: 'invoice_count', header: 'Fatura Sayısı', render: (s) => String(s.invoice_count) },
    {
      key: 'days_since_last',
      header: 'Son Faturadan Bu Yana',
      render: (s) => (s.days_since_last != null ? `${s.days_since_last} gün` : '-'),
    },
    { key: 'status', header: 'Durum', render: (s) => <StatusPill status={s.status} /> },
  ]

  return (
    <DataTable
      columns={columns}
      rows={filtered}
      status={status}
      onRetry={load}
      searchPlaceholder="Müşteri veya ürün ara..."
      searchValue={search}
      onSearchChange={setSearch}
      getRowKey={(s) => s.id}
      emptyMessage="Henüz abonelik kaydı yok."
    />
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/SubscriptionsTab.tsx
git commit -m "feat(muhasebe-frontend): add SubscriptionsTab with search and status pills"
```

---

### Task 8: ProductsTab

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/ProductsTab.tsx`

**Interfaces:**
- Consumes: `getProducts`, `Product` from `@/lib/api` (Task 1); `DataTable`, `DataTableColumn` from `./DataTable` (Task 4).
- Produces: `<ProductsTab />` — no props, self-contained.

- [ ] **Step 1: Create `src/components/dashboard/ProductsTab.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from './DataTable'
import { getProducts, type Product } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function ProductsTab() {
  const [products, setProducts] = useState<Product[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')

  async function load() {
    setStatus('loading')
    const data = await getProducts()
    if (data) {
      setProducts(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return products
    return products.filter(
      (p) => p.client_name.toLowerCase().includes(q) || p.product_name.toLowerCase().includes(q)
    )
  }, [products, search])

  const columns: DataTableColumn<Product>[] = [
    { key: 'client', header: 'Müşteri', render: (p) => p.client_name },
    { key: 'product', header: 'Ürün', render: (p) => p.product_name },
    { key: 'quantity', header: 'Adet', render: (p) => String(p.quantity) },
    {
      key: 'line_total',
      header: 'Tutar',
      render: (p) => (p.line_total != null ? `${p.line_total.toLocaleString('tr-TR')} ${p.currency}` : '-'),
    },
    { key: 'sale_date', header: 'Satış Tarihi', render: (p) => p.sale_date },
  ]

  return (
    <DataTable
      columns={columns}
      rows={filtered}
      status={status}
      onRetry={load}
      searchPlaceholder="Müşteri veya ürün ara..."
      searchValue={search}
      onSearchChange={setSearch}
      getRowKey={(p) => p.id}
      emptyMessage="Henüz ürün kaydı yok."
    />
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/ProductsTab.tsx
git commit -m "feat(muhasebe-frontend): add ProductsTab with search"
```

---

### Task 9: ComingSoonTab

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/ComingSoonTab.tsx`

**Interfaces:**
- Produces: `<ComingSoonTab />` — no props, self-contained.

- [ ] **Step 1: Create `src/components/dashboard/ComingSoonTab.tsx`**

```tsx
export function ComingSoonTab() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-24 text-center">
      <h2 className="text-lg font-semibold text-black/80 dark:text-white/90">Teklifler</h2>
      <p className="max-w-sm text-sm text-black/50 dark:text-white/50">
        Bu bölüm yakında geliyor — teklif takibi Kanban panosuyla burada olacak.
      </p>
    </div>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/ComingSoonTab.tsx
git commit -m "feat(muhasebe-frontend): add ComingSoonTab stub for the Teklifler tab"
```

---

### Task 10: Sidebar

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/Sidebar.tsx`

**Interfaces:**
- Consumes: `cn` from `@/lib/cn`.
- Produces:
  - `type DashboardTab = 'overview' | 'licenses' | 'subscriptions' | 'products' | 'offers'`
  - `<Sidebar active={DashboardTab} onSelect={(tab: DashboardTab) => void} onLogout={() => void} />`

- [ ] **Step 1: Create `src/components/dashboard/Sidebar.tsx`**

```tsx
import { FileText, KeyRound, LayoutGrid, LogOut, Package, RefreshCcw, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'

export type DashboardTab = 'overview' | 'licenses' | 'subscriptions' | 'products' | 'offers'

interface SidebarProps {
  active: DashboardTab
  onSelect: (tab: DashboardTab) => void
  onLogout: () => void
}

const ITEMS: { id: DashboardTab; label: string; icon: LucideIcon }[] = [
  { id: 'overview', label: 'Özet', icon: LayoutGrid },
  { id: 'licenses', label: 'Lisanslar', icon: KeyRound },
  { id: 'subscriptions', label: 'Abonelikler', icon: RefreshCcw },
  { id: 'products', label: 'Ürünler', icon: Package },
  { id: 'offers', label: 'Teklifler', icon: FileText },
]

export function Sidebar({ active, onSelect, onLogout }: SidebarProps) {
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col border-r border-black/5 bg-white/60 backdrop-blur-md dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 px-6 py-6">
        <img src="/static/images/logo.png" alt="Piramit Bilgisayar" className="h-8 dark:hidden" />
        <img src="/static/images/logo-dark.png" alt="Piramit Bilgisayar" className="hidden h-8 dark:block" />
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
              active === id
                ? 'bg-brand-soft text-brand dark:bg-brand/15'
                : 'text-black/60 hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/5'
            )}
          >
            <Icon className="h-5 w-5" strokeWidth={1.75} />
            {label}
          </button>
        ))}
      </nav>
      <div className="border-t border-black/5 p-3 dark:border-white/10">
        <button
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-black/60 transition-colors hover:bg-black/5 dark:text-white/60 dark:hover:bg-white/5"
        >
          <LogOut className="h-5 w-5" strokeWidth={1.75} />
          Çıkış Yap
        </button>
      </div>
    </aside>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/components/dashboard/Sidebar.tsx
git commit -m "feat(muhasebe-frontend): add dashboard Sidebar navigation"
```

---

### Task 11: DashboardPage

**Files:**
- Create: `muhasebe/frontend/src/pages/DashboardPage.tsx`

**Interfaces:**
- Consumes: `Sidebar`, `DashboardTab` from `@/components/dashboard/Sidebar` (Task 10); `OverviewTab` (Task 5); `LicensesTab` (Task 6); `SubscriptionsTab` (Task 7); `ProductsTab` (Task 8); `ComingSoonTab` (Task 9).
- Produces: `<DashboardPage onLogout={() => void} />`

- [ ] **Step 1: Create `src/pages/DashboardPage.tsx`**

```tsx
import { useState } from 'react'
import { Sidebar, type DashboardTab } from '@/components/dashboard/Sidebar'
import { OverviewTab } from '@/components/dashboard/OverviewTab'
import { LicensesTab } from '@/components/dashboard/LicensesTab'
import { SubscriptionsTab } from '@/components/dashboard/SubscriptionsTab'
import { ProductsTab } from '@/components/dashboard/ProductsTab'
import { ComingSoonTab } from '@/components/dashboard/ComingSoonTab'

interface DashboardPageProps {
  onLogout: () => void
}

const TITLES: Record<DashboardTab, string> = {
  overview: 'Özet',
  licenses: 'Lisanslar',
  subscriptions: 'Abonelikler',
  products: 'Ürünler',
  offers: 'Teklifler',
}

export function DashboardPage({ onLogout }: DashboardPageProps) {
  const [tab, setTab] = useState<DashboardTab>('overview')

  return (
    <div className="flex min-h-screen bg-bg dark:bg-neutral-950">
      <Sidebar active={tab} onSelect={setTab} onLogout={onLogout} />
      <main className="flex-1 overflow-y-auto px-8 py-8">
        <h1 className="mb-6 text-2xl font-semibold text-black/90 dark:text-white">{TITLES[tab]}</h1>
        {tab === 'overview' && <OverviewTab />}
        {tab === 'licenses' && <LicensesTab />}
        {tab === 'subscriptions' && <SubscriptionsTab />}
        {tab === 'products' && <ProductsTab />}
        {tab === 'offers' && <ComingSoonTab />}
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/pages/DashboardPage.tsx
git commit -m "feat(muhasebe-frontend): add DashboardPage wiring sidebar and tabs together"
```

---

### Task 12: Wire DashboardPage into App.tsx for the 'satis' role

**Files:**
- Modify: `muhasebe/frontend/src/App.tsx`

**Interfaces:**
- Consumes: `DashboardPage` from `@/pages/DashboardPage` (Task 11); existing `PlaceholderPanel`, `Role`, `checkAuth`/`logout` from Faz 1.
- Produces: nothing further consumes this — it's the final wiring point.

- [ ] **Step 1: Replace the `panel` step's render in `src/App.tsx`**

Add the import:

```tsx
import { DashboardPage } from '@/pages/DashboardPage'
```

Replace the existing panel block:

```tsx
      {step === 'panel' && role && (
        <PlaceholderPanel key="panel" role={role} onLogout={handleLogout} />
      )}
```

with:

```tsx
      {step === 'panel' && role === 'satis' && (
        <DashboardPage key="panel-satis" onLogout={handleLogout} />
      )}
      {step === 'panel' && role === 'yonetici' && (
        <PlaceholderPanel key="panel-yonetici" role={role} onLogout={handleLogout} />
      )}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0, no unused-import errors (`PlaceholderPanel` and `Role` are still used).

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/App.tsx
git commit -m "feat(muhasebe-frontend): render DashboardPage for the satis role"
```

---

### Task 13: Final production build and end-to-end manual verification

**Files:**
- No new files; build output only.

**Interfaces:**
- Consumes: everything from Tasks 1–12.

- [ ] **Step 1: Final production build**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 2: Start the app**

```bash
cd "C:\Claude 1\muhasebe"
python app.py
```

- [ ] **Step 3: Manual QA checklist (use the Browser preview tool)**

Log in, select "Satış ve Muhasebe" at the role-select screen, and verify each of the following:

- [ ] Dashboard loads with the sidebar (logo, 5 nav items, "Çıkış Yap" at the bottom) and lands on "Özet" by default.
- [ ] Özet tab shows 5 KPI cards with real numbers matching what `GET /api/stats` returns (check via `read_network_requests` or a direct `fetch` in `javascript_tool`).
- [ ] Lisanslar tab shows a table of real sales rows with correct status pills (color/label matching each row's `status` value) and a working search box (typing a known client or product name filters the rows).
- [ ] Abonelikler tab shows real subscription rows with status pills.
- [ ] Ürünler tab shows real product rows with formatted amounts (`line_total` + `currency`).
- [ ] Teklifler tab shows the "yakında geliyor" message, not a blank page or error.
- [ ] Simulate a fetch failure (e.g. temporarily block `/api/sales` via `read_network_requests`/dev tools, or stop the Python server mid-load) and confirm the Lisanslar tab shows "Veriler yüklenemedi" + a working "Tekrar dene" button that recovers once the server is back.
- [ ] Clicking "Çıkış Yap" in the sidebar returns to the login screen (same behavior as Faz 1's `PlaceholderPanel` logout).
- [ ] Dark mode (`localStorage.setItem('piramit.tema','koyu')` + reload) renders the sidebar, cards, and tables with legible contrast — no white-on-white or black-on-black text.
- [ ] Narrow viewport (375px) — the sidebar and tables remain usable (table scrolls horizontally inside its own container rather than breaking the page layout).

- [ ] **Step 4: Fix any failures found during QA, then re-run Step 3 until all boxes are checked.**

- [ ] **Step 5: Final commit**

```bash
cd "C:\Claude 1"
git add -A
git commit -m "chore(muhasebe-frontend): Dashboard verified end-to-end (overview, licenses, subscriptions, products, offers stub)"
```
