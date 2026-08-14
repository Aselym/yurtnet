# Muhasebe Mail Otomasyonu Modalı (Faz 2 — Alt-proje 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-row "send reminder" action to the Lisanslar tab that opens a confirmation modal showing the real recipient list before calling the existing backend reminder endpoint.

**Architecture:** `LicensesTab` gains an action column with a mail icon; clicking it opens `ReminderModal`, which fetches `GET /api/settings` to show the actual `internal_recipients` list, then on confirm calls the existing `POST /api/sales/{id}/send-reminder`. No backend changes.

**Tech Stack:** React 18, TypeScript, Tailwind CSS v4, `lucide-react`, existing `@/components/ui/*` primitives.

**Spec:** `docs/superpowers/specs/2026-08-14-muhasebe-mail-modal-faz2.md`

## Global Constraints

- Backend (`muhasebe/app.py`, `muhasebe/mailer.py`) is NOT modified — only `GET /api/settings` and `POST /api/sales/{id}/send-reminder` are consumed, exactly as they respond today.
- The button/modal is functionally an internal-team notification (goes to `internal_recipients`, not the customer) — this was explicitly confirmed with the user. The modal's copy must clearly state the real recipient list before sending, so the user always sees where the email actually goes.
- `stage` sent to the backend is computed client-side: `daysLeft <= 7 ? 'FINAL_REMINDER' : 'FIRST_REMINDER'` — matches `scheduler.py`'s own thresholds.
- No automated test framework this phase — verification is `npm run build` per task + final manual QA covering both a successful send and a failed send (e.g. missing SMTP config).
- Reuse Faz 1/Dashboard's brand tokens and `dark:` variant convention — no new tokens.
- Scope is Lisanslar only — Abonelikler/Ürünler get no equivalent action in this plan.

---

### Task 1: API client additions for settings and reminder sending

**Files:**
- Modify: `muhasebe/frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: existing `getJson<T>` helper (already in the file, from the Dashboard plan).
- Produces:
  - `type ReminderStage = 'FIRST_REMINDER' | 'FINAL_REMINDER'`
  - `getSettings(): Promise<Record<string, string> | null>`
  - `sendReminder(saleId: number, stage: ReminderStage): Promise<{ success: boolean; message: string }>`

- [ ] **Step 1: Append to `src/lib/api.ts`**

Add at the end of the file (after the existing `getProducts` function):

```ts
export type ReminderStage = 'FIRST_REMINDER' | 'FINAL_REMINDER'

export function getSettings(): Promise<Record<string, string> | null> {
  return getJson<Record<string, string>>('/api/settings')
}

export async function sendReminder(
  saleId: number,
  stage: ReminderStage
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch(`/api/sales/${saleId}/send-reminder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ stage }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Hatırlatma gönderildi.' : 'Gönderim başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}
```

- [ ] **Step 2: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0 (nothing imports the new functions yet).

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/lib/api.ts
git commit -m "feat(muhasebe-frontend): add getSettings/sendReminder to the API client"
```

---

### Task 2: ReminderModal component

**Files:**
- Create: `muhasebe/frontend/src/components/dashboard/ReminderModal.tsx`

**Interfaces:**
- Consumes: `getSettings`, `sendReminder`, `ReminderStage` from `@/lib/api` (Task 1); `Button`, `Card` from `@/components/ui/*`.
- Produces: `<ReminderModal saleId={number} clientName={string} productName={string} expirationDate={string} daysLeft={number} onClose={() => void} />`

- [ ] **Step 1: Create `src/components/dashboard/ReminderModal.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { getSettings, sendReminder, type ReminderStage } from '@/lib/api'

interface ReminderModalProps {
  saleId: number
  clientName: string
  productName: string
  expirationDate: string
  daysLeft: number
  onClose: () => void
}

type RecipientsStatus = 'loading' | 'error' | 'ready'
type SendStatus = 'idle' | 'sending' | 'success' | 'error'

export function ReminderModal({
  saleId,
  clientName,
  productName,
  expirationDate,
  daysLeft,
  onClose,
}: ReminderModalProps) {
  const [recipientsStatus, setRecipientsStatus] = useState<RecipientsStatus>('loading')
  const [recipients, setRecipients] = useState<string[]>([])
  const [sendStatus, setSendStatus] = useState<SendStatus>('idle')
  const [sendMessage, setSendMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    getSettings().then((settings) => {
      if (cancelled) return
      if (!settings) {
        setRecipientsStatus('error')
        return
      }
      const raw = settings.internal_recipients ?? ''
      const list = raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      setRecipients(list)
      setRecipientsStatus('ready')
    })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSend() {
    setSendStatus('sending')
    const stage: ReminderStage = daysLeft <= 7 ? 'FINAL_REMINDER' : 'FIRST_REMINDER'
    const result = await sendReminder(saleId, stage)
    setSendMessage(result.message)
    setSendStatus(result.success ? 'success' : 'error')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="w-full max-w-md p-6">
        <h2 className="mb-1 text-lg font-semibold text-black/90 dark:text-white">Hatırlatma Gönder</h2>
        <p className="mb-4 text-sm text-black/50 dark:text-white/50">
          {clientName} — {productName} ({expirationDate},{' '}
          {daysLeft >= 0 ? `${daysLeft} gün kaldı` : 'süresi doldu'})
        </p>

        {sendStatus === 'success' ? (
          <div className="space-y-4">
            <p className="text-sm text-emerald-600 dark:text-emerald-400">{sendMessage}</p>
            <Button className="w-full" onClick={onClose}>
              Kapat
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {recipientsStatus === 'loading' && (
              <p className="text-sm text-black/50 dark:text-white/50">Alıcı listesi yükleniyor...</p>
            )}
            {recipientsStatus === 'error' && (
              <p className="text-sm text-red-600 dark:text-red-400">Alıcı listesi yüklenemedi.</p>
            )}
            {recipientsStatus === 'ready' &&
              (recipients.length > 0 ? (
                <p className="text-sm text-black/70 dark:text-white/70">
                  Bu bildirim şu adreslere gidecek: <strong>{recipients.join(', ')}</strong>. Emin misiniz?
                </p>
              ) : (
                <p className="text-sm text-red-600 dark:text-red-400">
                  Alıcı listesi boş. Ayarlar sekmesinden iç bildirim adreslerini ekleyin.
                </p>
              ))}

            {sendStatus === 'error' && <p className="text-sm text-red-600 dark:text-red-400">{sendMessage}</p>}

            <div className="flex gap-3">
              <Button
                variant="ghost"
                className="flex-1"
                onClick={onClose}
                disabled={sendStatus === 'sending'}
              >
                Vazgeç
              </Button>
              <Button
                className="flex-1"
                onClick={handleSend}
                disabled={sendStatus === 'sending' || recipientsStatus !== 'ready' || recipients.length === 0}
              >
                {sendStatus === 'sending' ? 'Gönderiliyor...' : 'Tamam, Gönder'}
              </Button>
            </div>
          </div>
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
git add muhasebe/frontend/src/components/dashboard/ReminderModal.tsx
git commit -m "feat(muhasebe-frontend): add ReminderModal with real-recipient confirmation"
```

---

### Task 3: Wire the reminder action into LicensesTab

**Files:**
- Modify: `muhasebe/frontend/src/components/dashboard/LicensesTab.tsx`

**Interfaces:**
- Consumes: `ReminderModal` from `./ReminderModal` (Task 2); `Mail` icon from `lucide-react`.
- Produces: nothing further consumes this — it's the integration point for this plan.

- [ ] **Step 1: Replace the full contents of `src/components/dashboard/LicensesTab.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { Mail } from 'lucide-react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { ReminderModal } from './ReminderModal'
import { getSales, type Sale } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function LicensesTab() {
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')
  const [reminderSale, setReminderSale] = useState<Sale | null>(null)

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
    {
      key: 'actions',
      header: '',
      render: (s) => (
        <button
          onClick={() => setReminderSale(s)}
          title="Müşteriye Mail Gönder"
          className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
        >
          <Mail className="h-4 w-4" strokeWidth={1.75} />
        </button>
      ),
    },
  ]

  return (
    <>
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
      {reminderSale && (
        <ReminderModal
          saleId={reminderSale.id}
          clientName={reminderSale.client_name}
          productName={reminderSale.product_name}
          expirationDate={reminderSale.expiration_date}
          daysLeft={reminderSale.days_left}
          onClose={() => setReminderSale(null)}
        />
      )}
    </>
  )
}
```

Note: the hover style uses `text-brand-dark` (not `text-brand`) to match the WCAG-AA-safe pairing established for `bg-brand-soft` in the Dashboard plan's final-review fix.

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
git commit -m "feat(muhasebe-frontend): add mail action + ReminderModal wiring to LicensesTab"
```

---

### Task 4: Final production build and end-to-end manual verification

**Files:**
- No new files; build output only.

**Interfaces:**
- Consumes: everything from Tasks 1-3.

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

Log in, select "Satış ve Muhasebe", go to Lisanslar:

- [ ] Each row shows a mail icon action button that wasn't there before.
- [ ] Clicking it opens `ReminderModal` showing the correct client/product/expiration/days-left for that specific row.
- [ ] The modal correctly fetches and displays the real `internal_recipients` list from `/api/settings` (verify via `read_network_requests` that `GET /api/settings` fires and its response's `internal_recipients` value matches what's displayed).
- [ ] With a valid SMTP configuration (or by checking whatever the sandbox's `settings` table currently has), clicking "Tamam, Gönder" either shows a success message and lets you close the modal, OR shows the backend's real failure message (e.g. "SMTP sunucu adresi girilmemiş") without closing the modal — confirm which path the sandbox takes and that the UI behaves correctly for that path.
- [ ] If a failure message is shown, confirm you can dismiss and reopen the modal to retry.
- [ ] "Vazgeç" closes the modal without sending anything (confirm no `POST /api/sales/*/send-reminder` request fired).
- [ ] Dark mode: modal and action button are legible (no white-on-white/black-on-black), and the hover color on the mail icon passes the same contrast fix as the Dashboard's sidebar/StatCard (`text-brand-dark` in light mode).
- [ ] Narrow viewport (375px): modal remains fully visible and usable, not clipped or overflowing.

- [ ] **Step 4: Fix any failures found during QA, then re-run Step 3 until all boxes are checked.**

- [ ] **Step 5: Final commit**

```bash
cd "C:\Claude 1"
git add -A
git commit -m "chore(muhasebe-frontend): reminder modal verified end-to-end (recipient preview, send success/failure paths)"
```
