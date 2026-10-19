import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Check, ChevronDown, Info, Loader2, Search, X } from 'lucide-react'
import { clsx } from 'clsx'
import { useOutside } from '../../lib/hooks'
import { fmt as _fmt, fmtSpoken as _spoken } from '../../lib/format'
import type { ColType as _ColType } from '../../lib/api'

export function cn(...a: Parameters<typeof clsx>) {
  return clsx(...a)
}

// ------------------------------------------------------------------ Button
type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
export function Button({ variant = 'secondary', size = 'md', loading, icon, children, className, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md'; loading?: boolean; icon?: ReactNode }) {
  return (
    <button
      {...rest}
      disabled={rest.disabled || loading}
      className={cn(
        'inline-flex shrink-0 items-center justify-center gap-1.5 rounded-[var(--radius-ctl)] font-medium transition-colors disabled:opacity-50',
        size === 'sm' ? 'h-8 px-2.5 text-[13px]' : 'h-9 px-3.5 text-sm',
        variant === 'primary' && 'bg-brand font-semibold text-on-brand hover:brightness-105',
        variant === 'secondary' && 'border border-line-strong bg-surface text-ink hover:bg-surface-2',
        variant === 'ghost' && 'text-ink-2 hover:bg-surface-2 hover:text-ink',
        variant === 'danger' && 'border border-neg/40 bg-surface text-neg hover:bg-neg/5',
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

// ------------------------------------------------------------------ Panel
export function Panel({ title, hint, actions, children, className, bodyClass }: {
  title?: ReactNode; hint?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string
}) {
  return (
    <section className={cn('panel', className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="flex min-w-0 items-center gap-2">
            {title && <h2 className="truncate text-[15px] font-semibold text-ink">{title}</h2>}
            {hint && <InfoTip>{hint}</InfoTip>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn(bodyClass ?? 'p-5')}>{children}</div>
    </section>
  )
}

// ------------------------------------------------------------------ InfoTip
export function InfoTip({ children, side = 'bottom' }: { children: ReactNode; side?: 'bottom' | 'top' }) {
  return (
    <span className="group relative inline-flex">
      <button type="button" aria-label="Açıklama" className="text-muted hover:text-ink">
        <Info className="size-3.5" strokeWidth={2} />
      </button>
      <span
        role="tooltip"
        className={cn(
          // gizliyken yer kaplamasin (dar ekranda sayfayi yana tasiriyordu)
          'pointer-events-none absolute left-1/2 z-50 hidden w-72 max-w-[calc(100vw-6rem)] -translate-x-1/2 rounded-lg border border-line bg-surface px-3.5 py-2.5 text-[12.5px] leading-relaxed font-normal text-ink-2 shadow-[0_8px_30px_rgba(20,33,28,.12)] group-hover:block group-focus-within:block',
          side === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2',
        )}
      >
        {children}
      </span>
    </span>
  )
}

// ------------------------------------------------------------------ Segmented
export function Segmented<T extends string>({ value, onChange, options, size = 'md' }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; title?: string }[]; size?: 'sm' | 'md'
}) {
  return (
    <div role="radiogroup" className="inline-flex rounded-[var(--radius-ctl)] border border-line-strong bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={o.value === value}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cn(
            'rounded-[6px] font-medium whitespace-nowrap transition-colors',
            size === 'sm' ? 'px-2 py-1 text-[12px]' : 'px-3 py-1.5 text-[13px]',
            o.value === value ? 'bg-surface text-ink shadow-[0_1px_2px_rgba(20,33,28,.12)]' : 'text-ink-2 hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ Select (tekli)
export function Select<T extends string>({ value, onChange, options, label, className }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label?: string; className?: string
}) {
  return (
    <label className={cn('inline-flex max-w-full min-w-0 items-center gap-2 text-[13px] text-ink-2', className)}>
      {label}
      <span className="relative min-w-0">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as T)}
          className="h-9 max-w-full appearance-none truncate rounded-[var(--radius-ctl)] border border-line-strong bg-surface py-0 pr-8 pl-3 text-sm text-ink"
        >
          {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <ChevronDown className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted" />
      </span>
    </label>
  )
}

// ------------------------------------------------------------------ Popover
export function Popover({ trigger, children, align = 'left', width = 300, open: ctrlOpen, onOpenChange }: {
  trigger: (open: boolean, toggle: () => void) => ReactNode; children: (close: () => void) => ReactNode
  align?: 'left' | 'right'; width?: number; open?: boolean; onOpenChange?: (o: boolean) => void
}) {
  const [own, setOwn] = useState(false)
  const open = ctrlOpen ?? own
  const set = (o: boolean) => { if (ctrlOpen === undefined) setOwn(o); onOpenChange?.(o) }
  const ref = useRef<HTMLDivElement>(null)
  useOutside(ref, () => set(false), open)
  return (
    <div ref={ref} className="relative inline-flex">
      {trigger(open, () => set(!open))}
      {open && (
        <div
          style={{ width }}
          className={cn('absolute top-full z-40 mt-2 rounded-xl border border-line bg-surface shadow-[0_18px_50px_rgba(20,33,28,.16)]',
            align === 'right' ? 'right-0' : 'left-0')}
        >
          {children(() => set(false))}
        </div>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ OptionList (coklu secim, arama)
export interface Opt { value: string; label?: string; count?: number; hint?: string }

export function OptionList({ options, selected, onToggle, loading, search, onSearch, placeholder = 'Ara…', emptyText }: {
  options: Opt[]; selected: string[]; onToggle: (v: string) => void; loading?: boolean
  search: string; onSearch: (s: string) => void; placeholder?: string; emptyText?: string
}) {
  return (
    <div>
      <div className="flex items-center gap-2 border-b border-line px-3 py-2">
        <Search className="size-4 text-muted" />
        <input
          autoFocus
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder={placeholder}
          className="h-7 w-full bg-transparent text-sm outline-none placeholder:text-muted"
        />
        {loading && <Loader2 className="size-4 animate-spin text-muted" />}
      </div>
      <ul className="scroll-thin max-h-72 overflow-auto py-1">
        {options.length === 0 && !loading && (
          <li className="px-3 py-3 text-[13px] text-muted">{emptyText || 'Eşleşen kayıt yok.'}</li>
        )}
        {options.map((o) => {
          const on = selected.includes(o.value)
          return (
            <li key={o.value}>
              <button
                onClick={() => onToggle(o.value)}
                className="flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-[13px] hover:bg-surface-2"
              >
                <span className={cn('flex size-4 shrink-0 items-center justify-center rounded border',
                  on ? 'border-brand bg-brand text-on-brand' : 'border-line-strong')}>
                  {on && <Check className="size-3" strokeWidth={3} />}
                </span>
                <span className="min-w-0 flex-1 truncate text-ink">{o.label ?? o.value}</span>
                {o.count !== undefined && <span className="tnum text-[12px] text-muted">{o.count.toLocaleString('tr-TR')}</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ------------------------------------------------------------------ Drawer / Modal
export function Drawer({ open, onClose, title, subtitle, children, width = 720, actions }: {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; width?: number
  actions?: ReactNode
}) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', k)
    return () => document.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-[rgba(15,22,19,.32)]" onClick={onClose} />
      <aside style={{ width: `min(${width}px, 100vw)` }}
        className="drawer-in relative flex h-full flex-col border-l border-line bg-surface shadow-[-20px_0_60px_rgba(15,22,19,.18)]">
        <header className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
          <div className="min-w-0">
            <h2 className="display truncate text-xl font-semibold text-ink">{title}</h2>
            {subtitle && <div className="mt-0.5 text-[13px] text-ink-2">{subtitle}</div>}
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Kapat" icon={<X className="size-4" />} />
          </div>
        </header>
        <div className="scroll-thin flex-1 overflow-auto px-6 py-5">{children}</div>
      </aside>
    </div>
  )
}

export function Modal({ open, onClose, title, children, footer, width = 480 }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; width?: number
}) {
  useEffect(() => {
    if (!open) return
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', k)
    return () => document.removeEventListener('keydown', k)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-[rgba(15,22,19,.36)]" onClick={onClose} />
      <div style={{ width: `min(${width}px, 100%)` }} className="ledger-in relative rounded-2xl border border-line bg-surface shadow-[0_30px_80px_rgba(15,22,19,.25)]">
        <header className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Kapat" className="text-muted hover:text-ink"><X className="size-4" /></button>
        </header>
        <div className="px-5 py-4">{children}</div>
        {footer && <footer className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ Toast
type ToastItem = { id: number; text: string; tone: 'ok' | 'err' }
let push: ((t: Omit<ToastItem, 'id'>) => void) | null = null
export const toast = {
  ok: (text: string) => push?.({ text, tone: 'ok' }),
  err: (text: string) => push?.({ text, tone: 'err' }),
}
export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([])
  useEffect(() => {
    push = (t) => {
      const id = Date.now() + Math.random()
      setItems((p) => [...p, { ...t, id }])
      setTimeout(() => setItems((p) => p.filter((x) => x.id !== id)), t.tone === 'err' ? 7000 : 4000)
    }
    return () => { push = null }
  }, [])
  return (
    <div aria-live="polite" className="fixed right-5 bottom-5 z-[60] flex w-[min(380px,calc(100vw-40px))] flex-col gap-2">
      {items.map((t) => (
        <div key={t.id} className={cn('ledger-in rounded-xl border bg-surface px-4 py-3 text-[13.5px] shadow-[0_12px_40px_rgba(15,22,19,.18)]',
          t.tone === 'ok' ? 'border-pos/30 text-ink' : 'border-neg/40 text-ink')}>
          <span className={cn('mr-2 inline-block size-2 rounded-full align-middle', t.tone === 'ok' ? 'bg-pos' : 'bg-neg')} />
          {t.text}
        </div>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ durumlar
export function Loading({ label = 'Yükleniyor', className }: { label?: string; className?: string }) {
  return (
    <div className={cn('flex items-center justify-center gap-2 py-12 text-sm text-muted', className)}>
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  )
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <p className="max-w-md text-sm text-ink-2">{message}</p>
      {onRetry && <Button size="sm" onClick={onRetry}>Tekrar dene</Button>}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {children && <div className="max-w-md text-[13px] text-ink-2">{children}</div>}
    </div>
  )
}

export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'good' | 'warning' | 'serious' | 'critical' | 'brand'; children: ReactNode }) {
  const toneCls = {
    neutral: 'bg-surface-3 text-ink-2',
    good: 'bg-[color-mix(in_oklab,var(--good)_14%,transparent)] text-pos',
    warning: 'bg-[color-mix(in_oklab,var(--warning)_22%,transparent)] text-[#7a5300] dark:text-[#f3c35a]',
    serious: 'bg-[color-mix(in_oklab,var(--serious)_18%,transparent)] text-[#9a3f17] dark:text-[#f2a07c]',
    critical: 'bg-[color-mix(in_oklab,var(--critical)_14%,transparent)] text-neg',
    brand: 'bg-brand-soft text-brand-ink',
  }[tone]
  return <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium whitespace-nowrap', toneCls)}>{children}</span>
}

export function Field({ label, hint, children }: { label: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-ink">{label}</span>
      {children}
      {hint && <span className="text-[12px] leading-snug text-muted">{hint}</span>}
    </label>
  )
}

export const inputCls = 'h-9 w-full rounded-[var(--radius-ctl)] border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-muted'

// ------------------------------------------------------------------ Figure (buyuk rakam + Turkce okunusu)

/** Buyuk tutar: rakam (kurussuz) ve hemen altinda kucuk Turkce okunusu.
 *  "761.051.421 ₺" / "761 milyon 51 bin lira" */
export function Figure({ value, type = 'tl', className, spokenClass }: {
  value: unknown; type?: _ColType; className?: string; spokenClass?: string
}) {
  const sp = type === 'tl' || type === 'usd' ? _spoken(value, type) : null
  return (
    <>
      <span className={cn('tnum block', className)}>{_fmt(value, type)}</span>
      {sp && <span className={cn('block text-[12px] font-normal text-muted', spokenClass)}>{sp}</span>}
    </>
  )
}
