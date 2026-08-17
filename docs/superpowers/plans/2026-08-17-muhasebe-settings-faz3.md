# Ayarlar Modülü (Faz 3 / Alt-proje 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the missing Ayarlar (Settings) frontend for the muhasebe app — SMTP, Logo connection, account credentials, and auto-sync toggle — all against backend endpoints that already exist, and make the auto-sync toggle actually control the scheduler.

**Architecture:** A new `SettingsPage` reached from a small link on `RoleSelectPage` (third entry point alongside the two role circles). Four independent, self-contained cards (SMTP / Logo / Account / Sync schedule), each with its own local form state and its own save action against `POST /api/settings` or `POST /api/account`. One backend change: `scheduler.py`'s Logo sync loop checks the `logo_auto_sync` setting before running.

**Tech Stack:** React + TypeScript + Tailwind (existing `frontend/` app), Python `http.server` backend (existing `app.py`/`scheduler.py`/`database.py`), SQLite (`settings` table, already has all needed keys).

**Spec:** [docs/superpowers/specs/2026-08-17-muhasebe-settings-faz3-design.md](../specs/2026-08-17-muhasebe-settings-faz3-design.md)

## Global Constraints

- No automated test suite in this project (confirmed in every prior spec's Test section — "otomatik test paketi kurulmuyor"). Replace TDD test-first steps with: implement → `npx tsc --noEmit` → `npm run build` → manual browser verification via the Claude Browser tools → commit. This is the pattern used for every prior sub-project in this codebase this session.
- Follow existing component conventions exactly: `Card`/`Button`/`Input` from `frontend/src/components/ui/`, local form state via `useState` + an `update<K extends keyof typeof form>(key, value)` helper, `status: 'idle' | 'saving' | 'error'` per card, error message shown inline, matches `NewOfferModal.tsx` / `SetDurationModal.tsx` exactly.
- Password fields use `type="password"`, prefilled with the current stored value (plaintext storage is a known, accepted limitation — do not attempt to mask/omit prefill).
- Every card POSTs only its own keys to `/api/settings` — never the whole settings object (other cards' unsaved edits must not be clobbered).
- Turkish UI copy throughout, matching existing tone (see `ReminderModal.tsx`, `NewOfferModal.tsx` for examples).
- Build the frontend (`npm run build`) after every task that touches `frontend/`, so `muhasebe/static/` stays in sync — same as every prior commit this session.
- After the final task, restart the server via `preview_start` (per `[[feedback_dev_server_management]]` memory) — never `Bash`/`nohup`.

---

### Task 1: API client functions

**Files:**
- Modify: `muhasebe/frontend/src/lib/api.ts`

**Interfaces:**
- Consumes: existing `getSettings(): Promise<Record<string, string> | null>` (already defined, used by `ReminderModal.tsx` — do not redefine).
- Produces: `updateSettings`, `updateAccount`, `sendTestEmail`, `testLogoConnection`, `triggerLogoSync` — all used by Tasks 4-7.

- [ ] **Step 1: Add the five functions**

Add to `muhasebe/frontend/src/lib/api.ts`, near the existing `getSettings` function:

```typescript
export async function updateSettings(
  partial: Record<string, string>
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(partial),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Kaydedildi.' : 'Kayıt başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export interface UpdateAccountPayload {
  current_password: string
  new_username?: string
  new_password?: string
}

export async function updateAccount(
  payload: UpdateAccountPayload
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/account', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Hesap güncellendi.' : 'Güncelleme başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function sendTestEmail(recipients?: string): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/test-email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ recipients: recipients ?? '' }),
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Test e-postası gönderildi.' : 'Gönderim başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function testLogoConnection(): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/logo/test-connection', {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Bağlantı başarılı.' : 'Bağlantı başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function triggerLogoSync(): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/logo/sync', {
      method: 'POST',
      credentials: 'include',
    })
    const data = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Senkronizasyon tamamlandı.' : 'Senkronizasyon başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}
```

- [ ] **Step 2: Typecheck**

Run: `cd "C:/Claude 1/muhasebe/frontend" && npx tsc --noEmit`
Expected: no output (no errors). These functions aren't called yet, so nothing else can break.

- [ ] **Step 3: Commit**

```bash
git add muhasebe/frontend/src/lib/api.ts
git commit -m "feat(muhasebe-frontend): add settings/account/logo API client functions"
```

---

### Task 2: Routing — RoleSelectPage link + App.tsx settings step

**Files:**
- Modify: `muhasebe/frontend/src/pages/RoleSelectPage.tsx`
- Modify: `muhasebe/frontend/src/App.tsx`
- Create: `muhasebe/frontend/src/pages/SettingsPage.tsx` (stub only — full content in Task 3)

**Interfaces:**
- Produces: `SettingsPage` component with props `{ onBack: () => void }`, imported by `App.tsx`.
- Consumes: nothing new from other tasks.

- [ ] **Step 1: Add the stub SettingsPage**

Create `muhasebe/frontend/src/pages/SettingsPage.tsx`:

```tsx
import { Button } from '@/components/ui/button'
import { AnimatedBackground } from '@/components/AnimatedBackground'

interface SettingsPageProps {
  onBack: () => void
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-10">
      <AnimatedBackground />
      <div className="relative mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-display text-3xl italic text-black/90 dark:text-white">Ayarlar</h1>
          <Button variant="ghost" onClick={onBack}>
            Geri
          </Button>
        </div>
        <p className="text-sm text-black/50 dark:text-white/50">Yükleniyor...</p>
      </div>
    </div>
  )
}
```

This stub is intentionally minimal — Task 3 replaces the body with the real
data-loading + four cards. This step only proves the routing works before
adding data-fetching complexity.

- [ ] **Step 2: Add the "Ayarlar" link to RoleSelectPage**

In `muhasebe/frontend/src/pages/RoleSelectPage.tsx`, add a new prop and render
a small link below the two role buttons:

```tsx
interface RoleSelectPageProps {
  onSelect: (role: Role) => void
  onOpenSettings: () => void
}
```

Update the function signature:

```tsx
export function RoleSelectPage({ onSelect, onOpenSettings }: RoleSelectPageProps) {
```

Add this JSX right after the closing `</div>` of the `roles.map(...)` block
(the `<div className="relative flex flex-col gap-8 sm:flex-row sm:gap-12">...</div>`),
still inside the outer container:

```tsx
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        onClick={onOpenSettings}
        className="relative text-xs font-medium text-white/40 transition-colors hover:text-white/70"
      >
        ⚙ Ayarlar
      </motion.button>
```

- [ ] **Step 3: Wire the 'settings' step into App.tsx**

In `muhasebe/frontend/src/App.tsx`:

1. Add the import:
```tsx
import { SettingsPage } from '@/pages/SettingsPage'
```

2. Extend the `Step` type:
```tsx
type Step = 'checking' | 'login' | 'role-select' | 'transition' | 'panel' | 'settings'
```

3. Add a handler next to `handleRoleSelect`:
```tsx
  const handleOpenSettings = useCallback(() => setStep('settings'), [])
  const handleCloseSettings = useCallback(() => setStep('role-select'), [])
```

4. Pass the new prop to `RoleSelectPage` and add the settings render branch:
```tsx
      {step === 'role-select' && (
        <RoleSelectPage key="role-select" onSelect={handleRoleSelect} onOpenSettings={handleOpenSettings} />
      )}
```
(replacing the existing single-line `RoleSelectPage` render)

```tsx
      {step === 'settings' && <SettingsPage key="settings" onBack={handleCloseSettings} />}
```
(add this as a new branch, next to the other `{step === '...' && ...}` branches)

- [ ] **Step 4: Typecheck and build**

Run: `cd "C:/Claude 1/muhasebe/frontend" && npx tsc --noEmit && npm run build`
Expected: both succeed with no errors.

- [ ] **Step 5: Browser verification**

Use `preview_start` (per `[[feedback_dev_server_management]]` — never Bash)
to launch `license-reminder-app`, log in, and confirm:
- The role-select screen shows a small "⚙ Ayarlar" link below the two circles.
- Clicking it shows the stub Settings page with a working "Geri" button that
  returns to role-select.

- [ ] **Step 6: Commit**

```bash
git add muhasebe/frontend/src/pages/RoleSelectPage.tsx muhasebe/frontend/src/App.tsx muhasebe/frontend/src/pages/SettingsPage.tsx muhasebe/static/
git commit -m "feat(muhasebe-frontend): add Ayarlar entry point and routing stub"
```

---

### Task 3: SettingsPage data loading + four-card shell

**Files:**
- Modify: `muhasebe/frontend/src/pages/SettingsPage.tsx`

**Interfaces:**
- Consumes: `getSettings()` from `@/lib/api` (existing).
- Produces: passes `settings: Record<string, string>` and `onChanged: (patch: Record<string,string>) => void` to the four cards built in Tasks 4-7. Those tasks assume this exact shape.

- [ ] **Step 1: Replace SettingsPage with the real data-loading shell**

Replace the full contents of `muhasebe/frontend/src/pages/SettingsPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { AnimatedBackground } from '@/components/AnimatedBackground'
import { SmtpSettingsCard } from '@/components/settings/SmtpSettingsCard'
import { LogoSettingsCard } from '@/components/settings/LogoSettingsCard'
import { AccountSettingsCard } from '@/components/settings/AccountSettingsCard'
import { SyncScheduleCard } from '@/components/settings/SyncScheduleCard'
import { getSettings } from '@/lib/api'

interface SettingsPageProps {
  onBack: () => void
}

type Status = 'loading' | 'error' | 'ready'

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const data = await getSettings()
    if (data) {
      setSettings(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  function onChanged(patch: Record<string, string>) {
    setSettings((prev) => ({ ...prev, ...patch }))
  }

  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-10">
      <AnimatedBackground />
      <div className="relative mx-auto max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-3xl italic text-black/90 dark:text-white">Ayarlar</h1>
          <Button variant="ghost" onClick={onBack}>
            Geri
          </Button>
        </div>

        {status === 'loading' && <p className="text-sm text-white/60">Yükleniyor...</p>}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-white/10 p-10 text-center">
            <p className="text-sm text-white/60">Ayarlar yüklenemedi.</p>
            <Button variant="ghost" onClick={load}>
              Tekrar dene
            </Button>
          </div>
        )}

        {status === 'ready' && (
          <>
            <SmtpSettingsCard settings={settings} onChanged={onChanged} />
            <LogoSettingsCard settings={settings} onChanged={onChanged} />
            <AccountSettingsCard settings={settings} />
            <SyncScheduleCard settings={settings} onChanged={onChanged} />
          </>
        )}
      </div>
    </div>
  )
}
```

Note: this task references the four card components before they exist
(Tasks 4-7 create them). That's expected — Step 2 below will fail to
typecheck until those tasks land. This task's own verification is limited
to confirming the shell logic is correct; full typecheck happens at the
end of Task 7.

- [ ] **Step 2: Commit** (as part of the branch's history, not yet buildable standalone)

```bash
git add muhasebe/frontend/src/pages/SettingsPage.tsx
git commit -m "feat(muhasebe-frontend): wire SettingsPage data loading and card shell"
```

(A commit here is fine even though the build is red until Task 4 lands — matches
how multi-file features are built incrementally elsewhere in this repo's
history when tasks are executed sequentially in one sitting. If you are
executing tasks in strict one-commit-must-build order, merge Task 3's step 1
into Task 7 instead and skip this intermediate commit.)

---

### Task 4: SmtpSettingsCard

**Files:**
- Create: `muhasebe/frontend/src/components/settings/SmtpSettingsCard.tsx`

**Interfaces:**
- Consumes: `updateSettings`, `sendTestEmail` from `@/lib/api`; `settings: Record<string,string>` and `onChanged: (patch: Record<string,string>) => void` props (defined by Task 3).
- Produces: nothing consumed by later tasks — this card is a leaf.

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { sendTestEmail, updateSettings } from '@/lib/api'

interface SmtpSettingsCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type SaveStatus = 'idle' | 'saving' | 'error' | 'success'
type TestStatus = 'idle' | 'sending' | 'error' | 'success'

export function SmtpSettingsCard({ settings, onChanged }: SmtpSettingsCardProps) {
  const [form, setForm] = useState({
    smtp_host: settings.smtp_host ?? '',
    smtp_port: settings.smtp_port ?? '',
    smtp_user: settings.smtp_user ?? '',
    smtp_password: settings.smtp_password ?? '',
    sender_email: settings.sender_email ?? '',
    sender_name: settings.sender_name ?? '',
    internal_recipients: settings.internal_recipients ?? '',
  })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [saveMessage, setSaveMessage] = useState('')
  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testMessage, setTestMessage] = useState('')

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSave() {
    setSaveStatus('saving')
    const result = await updateSettings(form)
    if (result.success) {
      onChanged(form)
      setSaveStatus('success')
      setSaveMessage(result.message)
    } else {
      setSaveStatus('error')
      setSaveMessage(result.message)
    }
  }

  async function handleTest() {
    setTestStatus('sending')
    const result = await sendTestEmail(form.internal_recipients)
    setTestMessage(result.message)
    setTestStatus(result.success ? 'success' : 'error')
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">SMTP Ayarları</h2>
      <div className="space-y-3">
        <div className="flex gap-3">
          <Input
            placeholder="SMTP Sunucu"
            value={form.smtp_host}
            onChange={(e) => update('smtp_host', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Port"
            value={form.smtp_port}
            onChange={(e) => update('smtp_port', e.target.value)}
            className="w-24"
          />
        </div>
        <Input
          placeholder="SMTP Kullanıcı Adı"
          value={form.smtp_user}
          onChange={(e) => update('smtp_user', e.target.value)}
        />
        <Input
          type="password"
          placeholder="SMTP Şifre"
          value={form.smtp_password}
          onChange={(e) => update('smtp_password', e.target.value)}
        />
        <div className="flex gap-3">
          <Input
            placeholder="Gönderen E-posta"
            value={form.sender_email}
            onChange={(e) => update('sender_email', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Gönderen Adı"
            value={form.sender_name}
            onChange={(e) => update('sender_name', e.target.value)}
            className="flex-1"
          />
        </div>
        <Input
          placeholder="İç Bildirim Alıcıları (virgülle ayırın)"
          value={form.internal_recipients}
          onChange={(e) => update('internal_recipients', e.target.value)}
        />
      </div>

      {saveStatus === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{saveMessage}</p>}
      {saveStatus === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{saveMessage}</p>}
      {testStatus === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{testMessage}</p>}
      {testStatus === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{testMessage}</p>}

      <div className="mt-5 flex gap-3">
        <Button variant="ghost" className="flex-1" onClick={handleTest} disabled={testStatus === 'sending'}>
          {testStatus === 'sending' ? 'Gönderiliyor...' : 'Test E-postası Gönder'}
        </Button>
        <Button className="flex-1" onClick={handleSave} disabled={saveStatus === 'saving'}>
          {saveStatus === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
        </Button>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add muhasebe/frontend/src/components/settings/SmtpSettingsCard.tsx
git commit -m "feat(muhasebe-frontend): add SmtpSettingsCard"
```

---

### Task 5: LogoSettingsCard

**Files:**
- Create: `muhasebe/frontend/src/components/settings/LogoSettingsCard.tsx`

**Interfaces:**
- Consumes: `updateSettings`, `testLogoConnection`, `triggerLogoSync` from `@/lib/api`; same `settings`/`onChanged` props as Task 4.
- Produces: nothing consumed by later tasks — leaf component.

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { testLogoConnection, triggerLogoSync, updateSettings } from '@/lib/api'

interface LogoSettingsCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type SaveStatus = 'idle' | 'saving' | 'error' | 'success'
type ActionStatus = 'idle' | 'running' | 'error' | 'success'

export function LogoSettingsCard({ settings, onChanged }: LogoSettingsCardProps) {
  const [form, setForm] = useState({
    logo_sql_server: settings.logo_sql_server ?? '',
    logo_sql_port: settings.logo_sql_port ?? '',
    logo_sql_db: settings.logo_sql_db ?? '',
    logo_sql_user: settings.logo_sql_user ?? '',
    logo_sql_pass: settings.logo_sql_pass ?? '',
    logo_firm_no: settings.logo_firm_no ?? '',
    logo_period_no: settings.logo_period_no ?? '',
  })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [saveMessage, setSaveMessage] = useState('')
  const [testStatus, setTestStatus] = useState<ActionStatus>('idle')
  const [testMessage, setTestMessage] = useState('')
  const [syncStatus, setSyncStatus] = useState<ActionStatus>('idle')
  const [syncMessage, setSyncMessage] = useState('')

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSave() {
    setSaveStatus('saving')
    const result = await updateSettings(form)
    if (result.success) {
      onChanged(form)
      setSaveStatus('success')
    } else {
      setSaveStatus('error')
    }
    setSaveMessage(result.message)
  }

  async function handleTest() {
    setTestStatus('running')
    const result = await testLogoConnection()
    setTestMessage(result.message)
    setTestStatus(result.success ? 'success' : 'error')
  }

  async function handleSync() {
    setSyncStatus('running')
    const result = await triggerLogoSync()
    setSyncMessage(result.message)
    setSyncStatus(result.success ? 'success' : 'error')
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">Logo Bağlantı Ayarları</h2>
      <div className="space-y-3">
        <div className="flex gap-3">
          <Input
            placeholder="SQL Sunucu"
            value={form.logo_sql_server}
            onChange={(e) => update('logo_sql_server', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Port"
            value={form.logo_sql_port}
            onChange={(e) => update('logo_sql_port', e.target.value)}
            className="w-24"
          />
        </div>
        <Input
          placeholder="Veritabanı Adı"
          value={form.logo_sql_db}
          onChange={(e) => update('logo_sql_db', e.target.value)}
        />
        <Input
          placeholder="SQL Kullanıcı Adı"
          value={form.logo_sql_user}
          onChange={(e) => update('logo_sql_user', e.target.value)}
        />
        <Input
          type="password"
          placeholder="SQL Şifre"
          value={form.logo_sql_pass}
          onChange={(e) => update('logo_sql_pass', e.target.value)}
        />
        <div className="flex gap-3">
          <Input
            placeholder="Firma No"
            value={form.logo_firm_no}
            onChange={(e) => update('logo_firm_no', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Dönem No"
            value={form.logo_period_no}
            onChange={(e) => update('logo_period_no', e.target.value)}
            className="flex-1"
          />
        </div>
      </div>

      {saveStatus !== 'idle' && saveStatus !== 'saving' && (
        <p className={`mt-3 text-sm ${saveStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {saveMessage}
        </p>
      )}
      {testStatus !== 'idle' && testStatus !== 'running' && (
        <p className={`mt-3 text-sm ${testStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {testMessage}
        </p>
      )}
      {syncStatus !== 'idle' && syncStatus !== 'running' && (
        <p className={`mt-3 text-sm ${syncStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {syncMessage}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        <Button variant="ghost" className="flex-1" onClick={handleTest} disabled={testStatus === 'running'}>
          {testStatus === 'running' ? 'Test ediliyor...' : 'Bağlantıyı Test Et'}
        </Button>
        <Button variant="ghost" className="flex-1" onClick={handleSync} disabled={syncStatus === 'running'}>
          {syncStatus === 'running' ? 'Senkronize ediliyor...' : 'Şimdi Senkronize Et'}
        </Button>
        <Button className="flex-1" onClick={handleSave} disabled={saveStatus === 'saving'}>
          {saveStatus === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
        </Button>
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add muhasebe/frontend/src/components/settings/LogoSettingsCard.tsx
git commit -m "feat(muhasebe-frontend): add LogoSettingsCard"
```

---

### Task 6: AccountSettingsCard

**Files:**
- Create: `muhasebe/frontend/src/components/settings/AccountSettingsCard.tsx`

**Interfaces:**
- Consumes: `updateAccount` from `@/lib/api`; `settings: Record<string,string>` prop (reads `settings.admin_user` only — does not take `onChanged`, since it doesn't touch the generic settings map).
- Produces: nothing consumed by later tasks — leaf component.

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { updateAccount } from '@/lib/api'

interface AccountSettingsCardProps {
  settings: Record<string, string>
}

type Status = 'idle' | 'saving' | 'error' | 'success'

export function AccountSettingsCard({ settings }: AccountSettingsCardProps) {
  const [newUsername, setNewUsername] = useState(settings.admin_user ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')

  const canSubmit = currentPassword.trim() !== ''

  async function handleSave() {
    if (!canSubmit) return
    setStatus('saving')
    const result = await updateAccount({
      current_password: currentPassword,
      new_username: newUsername.trim() || undefined,
      new_password: newPassword.trim() || undefined,
    })
    setMessage(result.message)
    if (result.success) {
      setStatus('success')
      setCurrentPassword('')
      setNewPassword('')
    } else {
      setStatus('error')
    }
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">Hesap Bilgisi</h2>
      <div className="space-y-3">
        <Input
          placeholder="Kullanıcı Adı"
          value={newUsername}
          onChange={(e) => setNewUsername(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Yeni Şifre (opsiyonel)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Mevcut Şifre (onay için gerekli)"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
        />
      </div>

      {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}
      {status === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      <Button className="mt-5 w-full" onClick={handleSave} disabled={!canSubmit || status === 'saving'}>
        {status === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
      </Button>
    </Card>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add muhasebe/frontend/src/components/settings/AccountSettingsCard.tsx
git commit -m "feat(muhasebe-frontend): add AccountSettingsCard"
```

---

### Task 7: SyncScheduleCard + final frontend verification

**Files:**
- Create: `muhasebe/frontend/src/components/settings/SyncScheduleCard.tsx`

**Interfaces:**
- Consumes: `updateSettings` from `@/lib/api`; same `settings`/`onChanged` props as Task 4/5.
- Produces: nothing — leaf component. This is the last frontend task, so this
  step also runs the full typecheck/build now that all four cards imported
  by `SettingsPage.tsx` (Task 3) exist.

- [ ] **Step 1: Create the component**

```tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { updateSettings } from '@/lib/api'

interface SyncScheduleCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type Status = 'idle' | 'saving' | 'error'

export function SyncScheduleCard({ settings, onChanged }: SyncScheduleCardProps) {
  const [enabled, setEnabled] = useState((settings.logo_auto_sync ?? 'OFF') === 'ON')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')

  async function handleToggle(next: boolean) {
    setEnabled(next)
    setStatus('saving')
    const value = next ? 'ON' : 'OFF'
    const result = await updateSettings({ logo_auto_sync: value })
    if (result.success) {
      onChanged({ logo_auto_sync: value })
      setStatus('idle')
    } else {
      setEnabled(!next)
      setMessage(result.message)
      setStatus('error')
    }
  }

  return (
    <Card className="p-6">
      <h2 className="mb-1 text-sm font-semibold text-black/80 dark:text-white/90">Otomatik Senkronizasyon</h2>
      <p className="mb-4 text-xs text-black/40 dark:text-white/40">
        Açıkken Logo'dan lisans/abonelik/ürün verisi günde 3 kez (11:00, 15:00, 17:00) otomatik çekilir.
      </p>

      <label className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => handleToggle(e.target.checked)}
          disabled={status === 'saving'}
        />
        <span className="text-sm text-black/80 dark:text-white/80">
          {enabled ? 'Açık' : 'Kapalı'}
        </span>
      </label>

      {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}
    </Card>
  )
}
```

- [ ] **Step 2: Typecheck and build**

Run: `cd "C:/Claude 1/muhasebe/frontend" && npx tsc --noEmit && npm run build`
Expected: both succeed. This is the first point where `SettingsPage.tsx`
(Task 3) has all four of its imports satisfied — if there's a prop-shape
mismatch between what `SettingsPage.tsx` passes and what a card expects,
it surfaces here.

- [ ] **Step 3: Browser verification**

Use `preview_start` to launch/restart `license-reminder-app` (frontend-only
change, but restart anyway to serve the fresh `static/` build). Log in,
navigate to the role-select screen, click "⚙ Ayarlar", and confirm:
- All four cards render with the current values from `GET /api/settings`
  pre-filled (check against `muhasebe/license_reminders.db`'s `settings`
  table directly if unsure).
- Change one SMTP field and save; reload the page and confirm it persisted.
- Click "Bağlantıyı Test Et" on the Logo card (expect a real result — the
  session has live Logo SQL access per this conversation's history).
- Toggle the sync switch on the Sync card; confirm the checkbox reflects
  the new state after a page reload.
- Do **not** test "Test E-postası Gönder" yet — SMTP credentials are still
  placeholder values until the user fills in the real `lamborghini.com.tr`
  ones; a failure here is expected and not a bug.

- [ ] **Step 4: Commit**

```bash
git add muhasebe/frontend/src/components/settings/SyncScheduleCard.tsx muhasebe/static/
git commit -m "feat(muhasebe-frontend): add SyncScheduleCard, complete Ayarlar module"
```

---

### Task 8: Backend — make `logo_auto_sync` actually gate the scheduler

**Files:**
- Modify: `muhasebe/scheduler.py`

**Interfaces:**
- Consumes: `get_logo_settings()` from `logo_sync.py` (already imported indirectly — `scheduler.py` currently imports `sync_logo_invoices` etc. from `logo_sync`; add `get_logo_settings` to that import line).
- Produces: nothing new consumed elsewhere — this is the last task in the plan.

- [ ] **Step 1: Read the current loop**

Current `logo_sync_loop` in `muhasebe/scheduler.py` (for reference, already
in the file):

```python
def logo_sync_loop(check_interval_seconds=60):
    calisan_saatler = set()

    while True:
        try:
            now = datetime.now()
            anahtar = (now.date(), now.hour)
            if now.hour in LOGO_SYNC_SAATLERI and anahtar not in calisan_saatler:
                calisan_saatler.add(anahtar)
                eklenen, sure_bekleyen, atlanan = sync_logo_invoices()
                abone, riskli = sync_logo_subscriptions()
                urun, urun_atlanan = sync_logo_products()
                yenileme_adayi = yenileme_adaylari_bul()
                print(f"Logo senkronizasyonu ({now.hour}:00): {eklenen} lisans, "
                      f"{abone} abonelik, {urun} ürün, {yenileme_adayi} yenileme adayı.")
        except Exception as e:
            print(f"Logo Sync Scheduler Error: {e}")
        time.sleep(check_interval_seconds)
```

- [ ] **Step 2: Add the settings check**

Update the import line at the top of `muhasebe/scheduler.py`:

```python
from logo_sync import (sync_logo_invoices, sync_logo_subscriptions, sync_logo_products,
                       yenileme_adaylari_bul, get_logo_settings)
```

Replace the body of the `if now.hour in LOGO_SYNC_SAATLERI ...` block:

```python
            if now.hour in LOGO_SYNC_SAATLERI and anahtar not in calisan_saatler:
                calisan_saatler.add(anahtar)
                if get_logo_settings().get('logo_auto_sync') != 'ON':
                    print(f"Logo senkronizasyonu ({now.hour}:00): otomatik senkron kapalı, atlandı.")
                else:
                    eklenen, sure_bekleyen, atlanan = sync_logo_invoices()
                    abone, riskli = sync_logo_subscriptions()
                    urun, urun_atlanan = sync_logo_products()
                    yenileme_adayi = yenileme_adaylari_bul()
                    print(f"Logo senkronizasyonu ({now.hour}:00): {eklenen} lisans, "
                          f"{abone} abonelik, {urun} ürün, {yenileme_adayi} yenileme adayı.")
```

Note `calisan_saatler.add(anahtar)` stays **outside** the new `if/else` (it
already runs before the check) — this preserves the existing "mark this
hour as handled" behavior whether or not the sync actually ran, so a
disabled sync doesn't get retried every 60 seconds for the rest of that hour.

- [ ] **Step 3: Verify the default-OFF behavior manually**

Run:
```bash
cd "C:/Claude 1/muhasebe" && python -c "
from logo_sync import get_logo_settings
print(get_logo_settings().get('logo_auto_sync'))
"
```
Expected: `OFF` (the existing default from `database.py`'s
`default_settings` list — confirms sync will now be skipped until someone
turns it on via the new Sync card from Task 7).

- [ ] **Step 4: Restart the server and confirm no startup errors**

Use `preview_start` to restart `license-reminder-app`, then:
```bash
# check the preview logs for a clean startup — no traceback
```
(Use `mcp__Claude_Browser__preview_logs` with `level: "error"`, not Bash.)

- [ ] **Step 5: Commit**

```bash
git add muhasebe/scheduler.py
git commit -m "feat(muhasebe): gate automatic Logo sync on the logo_auto_sync setting"
```

---

## Final check (do this after Task 8, not as its own task)

Log in, open Ayarlar from the role-select screen, toggle "Otomatik
Senkronizasyon" to **On** (it will be Off by default post-deploy per Task 8's
Step 3 finding) — this is the one behavior change from this plan that has a
real-world consequence outside the app, so don't skip it.
