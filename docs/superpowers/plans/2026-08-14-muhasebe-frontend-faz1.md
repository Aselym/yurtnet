# Muhasebe Frontend Faz 1 (Giriş + Rol Seçimi) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `muhasebe/static/` (the current vanilla HTML/CSS/JS frontend) with a React + Vite login → rol seçimi → placeholder panel flow, without touching the Python backend's auth logic.

**Architecture:** New `muhasebe/frontend/` Vite+React+TypeScript project. `npm run build` writes directly into `muhasebe/static/` (`outDir: '../static'`, `base: '/static/'`), which `app.py`'s existing `do_GET` already serves unmodified for `/`, `/login`, `/dashboard`, and `/static/*`. No client-side router — a single in-memory state machine (`checking → login → role-select → transition → panel`) drives the four screens, since the backend only whitelists those four literal paths and there is nothing else to route between yet.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS v4 (`@tailwindcss/vite`), Framer Motion, hand-authored shadcn-style primitives (`class-variance-authority` + `clsx` + `tailwind-merge`, no interactive `shadcn` CLI), `lucide-react` for icons.

**Spec:** `docs/superpowers/specs/2026-08-14-muhasebe-frontend-faz1-design.md`

## Global Constraints

- Build output overwrites `muhasebe/static/` directly — confirmed acceptable, no staged preview path needed (see spec + brainstorming decision log).
- Brand color is `#f2691f` (`--brand` in the old `styles.css`) — reuse this exact value, do not invent a new one.
- Dark mode is opt-in via `data-theme="dark"` on `<html>`, driven by `localStorage['piramit.tema'] === 'koyu'` — reuse this exact mechanism, not `prefers-color-scheme`.
- Backend auth endpoints (`/api/login`, `/api/check-auth`, `/api/logout`) are not modified — their existing request/response shapes are contracts this frontend must match exactly (documented in Task 4).
- No automated test framework is introduced in this phase (matches the spec's explicit decision and the codebase's existing convention of zero test infrastructure). Verification is `npm run build` (catches TypeScript/build errors) plus manual Browser-preview QA in the final task.
- Role selection is client-side only (`sessionStorage`), never sent to the backend — there is no backend role/permission model.

---

### Task 1: Scaffold the Vite + React + TypeScript project

**Files:**
- Create: `muhasebe/frontend/` (via `npm create vite@latest`)
- Modify: `muhasebe/frontend/vite.config.ts`
- Modify: `muhasebe/frontend/tsconfig.app.json`
- Create: `muhasebe/frontend/public/images/` (copied from `muhasebe/static/images/`)

**Interfaces:**
- Produces: a working `npm run dev` and `npm run build` in `muhasebe/frontend/`, with the `@/*` import alias resolving to `muhasebe/frontend/src/*`, and `npm run build` writing to `muhasebe/static/`.

- [ ] **Step 1: Scaffold the project**

```bash
cd "C:\Claude 1\muhasebe"
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install dependencies**

```bash
npm install framer-motion clsx tailwind-merge class-variance-authority lucide-react
npm install -D tailwindcss @tailwindcss/vite
```

- [ ] **Step 3: Copy the existing brand images into `public/` so they survive the build**

Vite empties `outDir` before each build and only copies files that live under
`public/` verbatim into the output root. The logo files currently in
`muhasebe/static/images/` must move into `muhasebe/frontend/public/images/`
or they disappear the first time `npm run build` runs.

```bash
rm -rf "C:\Claude 1\muhasebe\frontend\public"
mkdir -p "C:\Claude 1\muhasebe\frontend\public\images"
cp -r "C:\Claude 1\muhasebe\static\images\." "C:\Claude 1\muhasebe\frontend\public\images\"
```

- [ ] **Step 4: Configure `vite.config.ts`**

Replace the file contents with:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

- [ ] **Step 5: Add the `@/*` path alias to TypeScript config**

In `muhasebe/frontend/tsconfig.app.json`, inside `"compilerOptions"`, add:

```json
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    },
```

- [ ] **Step 6: Verify the scaffold builds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0, prints a `../static/` output summary, and
`C:\Claude 1\muhasebe\static\index.html` now exists with a `<script type="module" src="/static/assets/...">` tag.

- [ ] **Step 7: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend muhasebe/static
git commit -m "feat(muhasebe-frontend): scaffold Vite+React+TS project building into muhasebe/static"
```

---

### Task 2: Brand theme tokens and dark mode

**Files:**
- Modify: `muhasebe/frontend/src/index.css`

**Interfaces:**
- Produces: Tailwind utility classes `bg-brand`, `text-brand`, `bg-bg`, etc. (via CSS `@theme` tokens), and a `dark:` variant that activates when `<html data-theme="dark">` is set — matching the old app's exact dark-mode trigger.

- [ ] **Step 1: Install and self-host the Inter font**

Spec requires Inter to be bundled, not loaded from a CDN, so the UI doesn't
depend on internet access at runtime. `@fontsource-variable/inter` ships the
actual `.woff2` files and imports them via CSS `@font-face`:

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm install @fontsource-variable/inter
```

- [ ] **Step 2: Replace `src/index.css`**

```css
@import "tailwindcss";
@import "@fontsource-variable/inter";

@custom-variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));

@theme {
  --color-brand: #f2691f;
  --color-brand-hover: #d95712;
  --color-brand-dark: #a8410c;
  --color-brand-soft: #fdf0e8;
  --color-bg: #f5f5f6;
  --font-sans: "InterVariable", ui-sans-serif, system-ui, -apple-system, sans-serif;
}

@layer base {
  body {
    @apply bg-bg font-sans antialiased;
  }
}
```

(`--color-bg` intentionally stays light here; dark-mode background is applied
per-screen with `dark:bg-neutral-950` utility classes in later tasks rather
than redefining the token, since Tailwind v4 `@theme` tokens are not
media/attribute-conditional themselves.)

- [ ] **Step 3: Verify Tailwind compiles the custom tokens and the font is bundled**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0. Inspect `../static/assets/*.css` and confirm it contains
`#f2691f` somewhere in the compiled output (`grep -c f2691f ../static/assets/*.css` should be ≥ 1),
and that `../static/assets/` now contains one or more `.woff2` files.

- [ ] **Step 4: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/package.json muhasebe/frontend/package-lock.json muhasebe/frontend/src/index.css
git commit -m "feat(muhasebe-frontend): self-host Inter font, add brand theme tokens and dark mode variant"
```

---

### Task 3: shadcn-style UI primitives (Button, Card, Input)

**Files:**
- Create: `muhasebe/frontend/src/lib/cn.ts`
- Create: `muhasebe/frontend/src/components/ui/button.tsx`
- Create: `muhasebe/frontend/src/components/ui/card.tsx`
- Create: `muhasebe/frontend/src/components/ui/input.tsx`

**Interfaces:**
- Produces:
  - `cn(...inputs: ClassValue[]): string`
  - `<Button variant="primary" | "ghost" size="default" | "lg" ...props />`
  - `<Card ...props />` (renders a `div`)
  - `<Input ...props />` (forwards ref, renders an `input`)

- [ ] **Step 1: Create the class-merging helper**

`muhasebe/frontend/src/lib/cn.ts`:

```ts
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 2: Create the Button primitive**

`muhasebe/frontend/src/components/ui/button.tsx`:

```tsx
import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-brand text-white hover:bg-brand-hover shadow-sm',
        ghost: 'text-black/70 hover:bg-black/5 dark:text-white/70 dark:hover:bg-white/10',
      },
      size: {
        default: 'h-11 px-5',
        lg: 'h-14 px-8 text-base',
      },
    },
    defaultVariants: { variant: 'primary', size: 'default' },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  )
)
Button.displayName = 'Button'
```

- [ ] **Step 3: Create the Card primitive**

`muhasebe/frontend/src/components/ui/card.tsx`:

```tsx
import * as React from 'react'
import { cn } from '@/lib/cn'

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-black/5 bg-white/80 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.08)] dark:bg-white/5 dark:border-white/10',
        className
      )}
      {...props}
    />
  )
}
```

- [ ] **Step 4: Create the Input primitive**

`muhasebe/frontend/src/components/ui/input.tsx`:

```tsx
import * as React from 'react'
import { cn } from '@/lib/cn'

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'flex h-11 w-full rounded-lg border border-black/10 bg-white px-3.5 text-sm text-black outline-none transition-colors placeholder:text-black/40 focus:border-brand focus:ring-2 focus:ring-brand/20 dark:bg-white/5 dark:border-white/10 dark:text-white dark:placeholder:text-white/40',
        className
      )}
      {...props}
    />
  )
)
Input.displayName = 'Input'
```

- [ ] **Step 5: Verify the build still succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0 (these files aren't imported anywhere yet, so this only checks for TypeScript syntax errors).

- [ ] **Step 6: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/lib/cn.ts muhasebe/frontend/src/components/ui
git commit -m "feat(muhasebe-frontend): add shadcn-style Button/Card/Input primitives"
```

---

### Task 4: Auth API client

**Files:**
- Create: `muhasebe/frontend/src/lib/auth.ts`

**Interfaces:**
- Consumes: existing backend endpoints — `GET /api/check-auth` → `{authenticated: boolean, user?: string}` (200) or `{authenticated: false}` (401); `POST /api/login` with JSON body `{username, password}` → `{success: boolean, message: string, redirect?: string}`; `POST /api/logout` → `{success: true, redirect: '/login', message: string}`. Session is an `HttpOnly` cookie the browser manages automatically — the client never reads or writes it directly, only sends `credentials: 'include'`.
- Produces:
  - `checkAuth(): Promise<boolean>`
  - `login(username: string, password: string): Promise<{success: boolean; message: string}>`
  - `logout(): Promise<void>`

- [ ] **Step 1: Create `src/lib/auth.ts`**

```ts
interface CheckAuthResponse {
  authenticated: boolean
  user?: string
}

interface LoginResponse {
  success: boolean
  message?: string
}

export async function checkAuth(): Promise<boolean> {
  try {
    const res = await fetch('/api/check-auth', { credentials: 'include' })
    if (!res.ok) return false
    const data: CheckAuthResponse = await res.json()
    return data.authenticated === true
  } catch {
    return false
  }
}

export async function login(
  username: string,
  password: string
): Promise<{ success: boolean; message: string }> {
  try {
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    })
    const data: LoginResponse = await res.json()
    return {
      success: !!data.success,
      message: data.message ?? (res.ok ? 'Giriş başarılı.' : 'Giriş başarısız.'),
    }
  } catch {
    return { success: false, message: 'Sunucuya ulaşılamıyor. Bağlantınızı kontrol edin.' }
  }
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/logout', { method: 'POST', credentials: 'include' })
  } catch {
    // Sessizce geç: yerel oturum durumu zaten temizlenecek.
  }
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
git add muhasebe/frontend/src/lib/auth.ts
git commit -m "feat(muhasebe-frontend): add auth API client wrapping /api/login,check-auth,logout"
```

---

### Task 5: Role type and LoginPage

**Files:**
- Create: `muhasebe/frontend/src/lib/types.ts`
- Create: `muhasebe/frontend/src/pages/LoginPage.tsx`

**Interfaces:**
- Consumes: `login` from `@/lib/auth` (Task 4); `Button`, `Card`, `Input` from `@/components/ui/*` (Task 3).
- Produces:
  - `Role = 'yonetici' | 'satis'` (exported from `@/lib/types`)
  - `<LoginPage onSuccess={() => void} />`

- [ ] **Step 1: Create `src/lib/types.ts`**

```ts
export type Role = 'yonetici' | 'satis'
```

- [ ] **Step 2: Create `src/pages/LoginPage.tsx`**

```tsx
import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { login } from '@/lib/auth'

interface LoginPageProps {
  onSuccess: () => void
}

export function LoginPage({ onSuccess }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const result = await login(username, password)
    setSubmitting(false)
    if (result.success) {
      onSuccess()
    } else {
      setError(result.message)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-bg px-4 dark:bg-neutral-950">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(242,105,31,0.12),transparent_45%),radial-gradient(circle_at_80%_80%,rgba(242,105,31,0.10),transparent_45%)]" />
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <Card className="w-[380px] p-8">
          <div className="mb-8 flex flex-col items-center text-center">
            <img src="/static/images/logo.png" alt="Piramit Bilgisayar" className="mb-4 h-12" />
            <h1 className="text-lg font-semibold text-black/90 dark:text-white">Piramit Lisans Takip</h1>
            <p className="mt-1 text-sm text-black/50 dark:text-white/50">
              Lisans &amp; Süre Sonu Takip Platformu
            </p>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 rounded-lg bg-red-50 px-3.5 py-2.5 text-sm text-red-600 dark:bg-red-500/10 dark:text-red-400"
            >
              {error}
            </motion.div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-black/70 dark:text-white/70">
                Kullanıcı Adı
              </label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-black/70 dark:text-white/70">
                Şifre
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            <Button type="submit" size="lg" className="mt-2 w-full" disabled={submitting}>
              {submitting ? 'Giriş yapılıyor...' : 'Giriş Yap'}
            </Button>
          </form>
        </Card>
      </motion.div>
    </div>
  )
}
```

- [ ] **Step 3: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0.

- [ ] **Step 4: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/lib/types.ts muhasebe/frontend/src/pages/LoginPage.tsx
git commit -m "feat(muhasebe-frontend): add LoginPage wired to the existing /api/login endpoint"
```

---

### Task 6: RoleSelectPage

**Files:**
- Create: `muhasebe/frontend/src/pages/RoleSelectPage.tsx`

**Interfaces:**
- Consumes: `Role` from `@/lib/types` (Task 5); `LayoutDashboard`, `Users` icons from `lucide-react`.
- Produces: `<RoleSelectPage onSelect={(role: Role) => void} />`

- [ ] **Step 1: Create `src/pages/RoleSelectPage.tsx`**

```tsx
import { motion } from 'framer-motion'
import { LayoutDashboard, Users, type LucideIcon } from 'lucide-react'
import type { Role } from '@/lib/types'

interface RoleSelectPageProps {
  onSelect: (role: Role) => void
}

const roles: { id: Role; label: string; icon: LucideIcon }[] = [
  { id: 'yonetici', label: 'Yönetici Girişi', icon: LayoutDashboard },
  { id: 'satis', label: 'Satış ve Muhasebe', icon: Users },
]

export function RoleSelectPage({ onSelect }: RoleSelectPageProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-12 bg-bg px-4 dark:bg-neutral-950">
      <motion.h1
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-xl font-semibold text-black/80 dark:text-white/90"
      >
        Nasıl devam etmek istersiniz?
      </motion.h1>
      <div className="flex flex-col gap-8 sm:flex-row sm:gap-12">
        {roles.map(({ id, label, icon: Icon }, i) => (
          <motion.button
            key={id}
            initial={{ opacity: 0, y: 24, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.45, delay: i * 0.12, ease: 'easeOut' }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onSelect(id)}
            className="group flex h-48 w-48 flex-col items-center justify-center gap-3 rounded-full border border-black/5 bg-white text-black/80 shadow-[0_12px_40px_rgba(0,0,0,0.08)] transition-colors hover:border-brand/40 hover:text-brand dark:border-white/10 dark:bg-white/5 dark:text-white/80"
          >
            <Icon className="h-10 w-10 text-brand transition-transform group-hover:scale-110" strokeWidth={1.5} />
            <span className="px-4 text-center text-sm font-medium">{label}</span>
          </motion.button>
        ))}
      </div>
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
git add muhasebe/frontend/src/pages/RoleSelectPage.tsx
git commit -m "feat(muhasebe-frontend): add RoleSelectPage with animated circular role buttons"
```

---

### Task 7: LoadingTransition

**Files:**
- Create: `muhasebe/frontend/src/pages/LoadingTransition.tsx`

**Interfaces:**
- Produces: `<LoadingTransition onDone={() => void} durationMs?: number />` — calls `onDone` once, `durationMs` (default 3000) after mount.

- [ ] **Step 1: Create `src/pages/LoadingTransition.tsx`**

```tsx
import { useEffect } from 'react'
import { motion } from 'framer-motion'

interface LoadingTransitionProps {
  onDone: () => void
  durationMs?: number
}

export function LoadingTransition({ onDone, durationMs = 3000 }: LoadingTransitionProps) {
  useEffect(() => {
    const timer = setTimeout(onDone, durationMs)
    return () => clearTimeout(timer)
  }, [onDone, durationMs])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg dark:bg-neutral-950"
    >
      <motion.img
        src="/static/images/logo.png"
        alt="Piramit Bilgisayar"
        className="h-14"
        animate={{ scale: [1, 1.06, 1] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div className="relative h-1 w-56 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-brand"
          initial={{ width: '0%' }}
          animate={{ width: '100%' }}
          transition={{ duration: durationMs / 1000, ease: 'easeInOut' }}
        />
      </div>
      <p className="text-sm text-black/50 dark:text-white/50">Panele hazırlanıyor...</p>
    </motion.div>
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
git add muhasebe/frontend/src/pages/LoadingTransition.tsx
git commit -m "feat(muhasebe-frontend): add 3s branded LoadingTransition screen"
```

---

### Task 8: PlaceholderPanel

**Files:**
- Create: `muhasebe/frontend/src/pages/PlaceholderPanel.tsx`

**Interfaces:**
- Consumes: `Role` from `@/lib/types`; `Button` from `@/components/ui/button`.
- Produces: `<PlaceholderPanel role={Role} onLogout={() => void} />`

- [ ] **Step 1: Create `src/pages/PlaceholderPanel.tsx`**

```tsx
import { Button } from '@/components/ui/button'
import type { Role } from '@/lib/types'

interface PlaceholderPanelProps {
  role: Role
  onLogout: () => void
}

const roleLabels: Record<Role, string> = {
  yonetici: 'Yönetici Paneli',
  satis: 'Satış ve Muhasebe Paneli',
}

export function PlaceholderPanel({ role, onLogout }: PlaceholderPanelProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-4 text-center dark:bg-neutral-950">
      <h1 className="text-2xl font-semibold text-black/80 dark:text-white/90">{roleLabels[role]}</h1>
      <p className="max-w-md text-sm text-black/50 dark:text-white/50">
        Bu ekran Faz 2/3'te gerçek içerikle değiştirilecek. Giriş ve rol seçimi akışı burada test edilebilir.
      </p>
      <Button variant="ghost" onClick={onLogout} className="mt-4">
        Çıkış Yap
      </Button>
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
git add muhasebe/frontend/src/pages/PlaceholderPanel.tsx
git commit -m "feat(muhasebe-frontend): add PlaceholderPanel stub for Faz 2/3 destinations"
```

---

### Task 9: App state machine wiring everything together

**Files:**
- Modify: `muhasebe/frontend/src/App.tsx`
- Modify: `muhasebe/frontend/src/main.tsx`
- Modify: `muhasebe/frontend/index.html`
- Delete: `muhasebe/frontend/src/App.css` (Vite scaffold default, unused)
- Delete: `muhasebe/frontend/src/assets/react.svg` (Vite scaffold default, unused)

**Interfaces:**
- Consumes: `checkAuth`, `logout` from `@/lib/auth` (Task 4); `LoginPage` (Task 5); `RoleSelectPage` (Task 6); `LoadingTransition` (Task 7); `PlaceholderPanel` (Task 8); `Role` from `@/lib/types`.
- Produces: the assembled app — no further tasks consume this.

- [ ] **Step 1: Remove unused Vite scaffold files**

```bash
cd "C:\Claude 1\muhasebe\frontend"
rm -f src/App.css
rm -rf src/assets
```

- [ ] **Step 2: Replace `src/App.tsx`**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { LoginPage } from '@/pages/LoginPage'
import { RoleSelectPage } from '@/pages/RoleSelectPage'
import { LoadingTransition } from '@/pages/LoadingTransition'
import { PlaceholderPanel } from '@/pages/PlaceholderPanel'
import { checkAuth, logout } from '@/lib/auth'
import type { Role } from '@/lib/types'

type Step = 'checking' | 'login' | 'role-select' | 'transition' | 'panel'

const ROLE_STORAGE_KEY = 'piramit.rol'

export default function App() {
  const [step, setStep] = useState<Step>('checking')
  const [role, setRole] = useState<Role | null>(null)

  useEffect(() => {
    let cancelled = false
    checkAuth().then((authenticated) => {
      if (cancelled) return
      if (!authenticated) {
        setStep('login')
        return
      }
      const storedRole = sessionStorage.getItem(ROLE_STORAGE_KEY) as Role | null
      if (storedRole === 'yonetici' || storedRole === 'satis') {
        setRole(storedRole)
        setStep('panel')
      } else {
        setStep('role-select')
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const handleLoginSuccess = useCallback(() => setStep('role-select'), [])

  const handleRoleSelect = useCallback((selected: Role) => {
    sessionStorage.setItem(ROLE_STORAGE_KEY, selected)
    setRole(selected)
    setStep('transition')
  }, [])

  const handleTransitionDone = useCallback(() => setStep('panel'), [])

  const handleLogout = useCallback(async () => {
    await logout()
    sessionStorage.removeItem(ROLE_STORAGE_KEY)
    setRole(null)
    setStep('login')
  }, [])

  return (
    <AnimatePresence mode="wait">
      {step === 'checking' && <div key="checking" className="min-h-screen bg-bg dark:bg-neutral-950" />}
      {step === 'login' && <LoginPage key="login" onSuccess={handleLoginSuccess} />}
      {step === 'role-select' && <RoleSelectPage key="role-select" onSelect={handleRoleSelect} />}
      {step === 'transition' && <LoadingTransition key="transition" onDone={handleTransitionDone} />}
      {step === 'panel' && role && (
        <PlaceholderPanel key="panel" role={role} onLogout={handleLogout} />
      )}
    </AnimatePresence>
  )
}
```

- [ ] **Step 3: Replace `src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
)
```

- [ ] **Step 4: Replace `index.html`**

```html
<!doctype html>
<html lang="tr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Piramit Lisans Takip</title>
    <link rel="icon" type="image/png" href="/static/images/logo2.png" />
    <script>
      try {
        if (localStorage.getItem('piramit.tema') === 'koyu') {
          document.documentElement.setAttribute('data-theme', 'dark')
        }
      } catch (e) {}
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Verify the build succeeds**

```bash
cd "C:\Claude 1\muhasebe\frontend"
npm run build
```

Expected: exits 0, no unused-import or type errors.

- [ ] **Step 6: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/frontend/src/App.tsx muhasebe/frontend/src/main.tsx muhasebe/frontend/index.html
git add -u muhasebe/frontend/src
git commit -m "feat(muhasebe-frontend): wire login/role-select/loading/panel state machine in App"
```

---

### Task 10: Backend MIME type support for Vite's build assets

**Files:**
- Modify: `muhasebe/app.py:87-96` (the `/static/` branch of `do_GET`)

**Interfaces:**
- Consumes: nothing new.
- Produces: correct `Content-Type` for `.woff2`, `.json`, and `.map` files under `/static/`, which Vite's build emits (fonts, and optionally source maps/manifests) and the old MIME map didn't cover (it fell through to `text/html`, which browsers refuse to run/parse as JS, CSS, or a font).

- [ ] **Step 1: Extend the MIME type ladder**

In `muhasebe/app.py`, replace:

```python
            mime = 'text/css; charset=utf-8' if path.endswith('.css') else \
                   'application/javascript; charset=utf-8' if path.endswith('.js') else \
                   'image/png' if path.endswith('.png') else \
                   'image/svg+xml' if path.endswith('.svg') else \
                   'image/jpeg' if path.endswith(('.jpg', '.jpeg')) else 'text/html'
```

with:

```python
            mime = 'text/css; charset=utf-8' if path.endswith('.css') else \
                   'application/javascript; charset=utf-8' if path.endswith('.js') else \
                   'image/png' if path.endswith('.png') else \
                   'image/svg+xml' if path.endswith('.svg') else \
                   'image/jpeg' if path.endswith(('.jpg', '.jpeg')) else \
                   'font/woff2' if path.endswith('.woff2') else \
                   'application/json; charset=utf-8' if path.endswith('.json') else \
                   'application/json; charset=utf-8' if path.endswith('.map') else 'text/html'
```

- [ ] **Step 2: Verify manually**

Start the app and confirm the built JS bundle is served with the right
content type (the codebase has no existing test suite, so this is checked
directly against the running server, consistent with how the rest of
`app.py` is verified elsewhere in this project):

```bash
cd "C:\Claude 1\muhasebe"
python app.py &
sleep 1
curl -sI http://localhost:5000/static/index.html | grep -i content-type
BUNDLE=$(curl -s http://localhost:5000/static/index.html | grep -oE '/static/assets/[a-zA-Z0-9_.-]+\.js' | head -1)
curl -sI "http://localhost:5000$BUNDLE" | grep -i content-type
kill %1
```

Expected: the `.js` bundle line reports `Content-Type: application/javascript; charset=utf-8`.

- [ ] **Step 3: Commit**

```bash
cd "C:\Claude 1"
git add muhasebe/app.py
git commit -m "fix(muhasebe): serve .woff2/.json/.map with correct content-type for Vite assets"
```

---

### Task 11: Full production build and end-to-end manual verification

**Files:**
- Modify: `muhasebe/frontend/dist` is not used (build goes straight to `../static`); no new files.

**Interfaces:**
- Consumes: the entire app from Tasks 1–10.
- Produces: a verified, working `muhasebe/static/` ready for the accounting PC.

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

Open `http://localhost:5000/` and verify each of the following, checking
them off as they pass:

- [ ] Not logged in → the branded login card appears (logo, title, subtitle), not a blank page.
- [ ] Submitting wrong credentials shows the inline red error banner with the backend's message, form stays usable.
- [ ] Submitting correct credentials transitions to the "Nasıl devam etmek istersiniz?" role-select screen with the two animated circular buttons.
- [ ] Clicking a role button plays the ~3s LoadingTransition (pulsing logo, filling progress bar) then lands on the matching PlaceholderPanel ("Yönetici Paneli" or "Satış ve Muhasebe Paneli").
- [ ] Reloading the page while on the placeholder panel skips straight back to the same panel (no re-login, no re-role-select) — confirms `sessionStorage` + `checkAuth` short-circuit works.
- [ ] Clicking "Çıkış Yap" returns to the login screen, and reloading afterward stays on the login screen (session actually cleared).
- [ ] Running `localStorage.setItem('piramit.tema','koyu')` in the browser console, then reloading, renders every screen in dark mode with legible contrast (no white-on-white or black-on-black text).
- [ ] Resizing the browser to a narrow mobile width keeps the login card and role buttons usable (buttons stack vertically, nothing overflows horizontally).

- [ ] **Step 4: Fix any failures found during QA, then re-run Step 3 until all boxes are checked.**

- [ ] **Step 5: Final commit**

```bash
cd "C:\Claude 1"
git add -A
git commit -m "chore(muhasebe-frontend): Faz 1 verified end-to-end (login, role select, loading, placeholder panels)"
```
