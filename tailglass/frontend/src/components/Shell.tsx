import { CompanyBadge, PRODUCT, TailglassLogo, TailglassMark } from './Brand'
import { useEffect, useState, type ReactNode } from 'react'
import {
  BarChart3, Boxes, FileSpreadsheet, Shapes, FileText, LayoutDashboard, LogOut, Moon,
  PackageCheck, RefreshCw, Repeat, Settings, ShoppingCart, Sun, Truck, UserRound, Users,
} from 'lucide-react'
import { api } from '../lib/api'
import { navigate } from '../lib/router'
import { useWork, type Currency } from '../lib/state'
import { PeriodStrip } from './PeriodStrip'
import { Segmented, cn, toast } from './ui'

export const NAV: { group: string; items: { key: string; label: string; icon: typeof Users }[] }[] = [
  { group: 'Başlangıç', items: [{ key: 'studyo', label: 'Analiz stüdyosu', icon: Shapes }, { key: 'genel', label: 'Genel bakış', icon: LayoutDashboard }] },
  {
    group: 'Hareketler', items: [
      { key: 'satislar', label: 'Satışlar', icon: ShoppingCart },
      { key: 'alislar', label: 'Alışlar', icon: Truck },
    ],
  },
  {
    group: 'Katalog', items: [
      { key: 'stok', label: 'Ürünler ve stok', icon: Boxes },
      { key: 'musteriler', label: 'Müşteriler', icon: Users },
    ],
  },
  {
    group: 'Raporlar', items: [
      { key: 'analiz', label: 'Analiz', icon: BarChart3 },
      { key: 'donem', label: 'Dönem raporu', icon: FileSpreadsheet },
    ],
  },
  {
    group: 'Takip', items: [
      { key: 'lisanslar', label: 'Lisanslar', icon: PackageCheck },
      { key: 'abonelikler', label: 'Abonelikler', icon: Repeat },
      { key: 'teklifler', label: 'Teklifler', icon: FileText },
      { key: 'temsilciler', label: 'Temsilciler', icon: UserRound },
    ],
  },
]

export const PAGE_TITLE: Record<string, string> = Object.fromEntries(
  [...NAV.flatMap((g) => g.items.map((i) => [i.key, i.label])), ['ayarlar', 'Ayarlar']],
)

// Donemden bagimsiz sayfalar ust seridi gostermez
const DONEMSIZ = new Set(['studyo', 'ayarlar', 'teklifler', 'lisanslar', 'abonelikler'])

export function Shell({ page, children, onLogout }: { page: string; children: ReactNode; onLogout: () => void }) {
  const { meta, currency, setCurrency } = useWork()
  const [dark, setDark] = useState(() => document.documentElement.getAttribute('data-theme') === 'dark')
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
    try { localStorage.setItem('defter.tema', dark ? 'koyu' : 'acik') } catch { /* yok say */ }
  }, [dark])

  const company = meta?.settings?.company_name || ''

  return (
    <div className="flex h-full">
      <aside className="no-print flex w-[232px] shrink-0 flex-col border-r border-line bg-surface/85 backdrop-blur max-lg:w-[68px]">
        {/* Lisans sahibi sirket (Ayarlar > Sirket). Urun markasi sag ustte. */}
        <div className="px-4 pt-5 pb-3 max-lg:hidden">
          <CompanyBadge name={company} logo={meta?.settings?.company_logo} logoDark={meta?.settings?.company_logo_dark} />
          {company && meta?.settings?.company_logo && <p className="mt-1.5 truncate text-[12px] text-muted">{company}</p>}
        </div>
        <div className="hidden justify-center pt-4 pb-2 max-lg:flex"><TailglassMark size={30} /></div>
        <nav className="scroll-thin flex-1 overflow-y-auto px-2.5 pb-4" aria-label="Ana menü">
          {NAV.map((g) => (
            <div key={g.group} className="mt-3">
              <p className="px-2 pb-1 text-[11.5px] font-medium text-muted max-lg:hidden">{g.group}</p>
              {g.items.map((it) => {
                const on = page === it.key
                return (
                  <a key={it.key} href={`#/${it.key}`} aria-current={on ? 'page' : undefined} title={it.label}
                    className={cn('relative flex items-center gap-2.5 rounded-[var(--radius-panel)] px-2.5 py-2 text-[13.5px] transition-colors max-lg:justify-center',
                      on ? 'bg-brand-soft font-semibold text-brand-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink')}>
                    {on && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r bg-brand" />}
                    <it.icon className="size-[18px] shrink-0" strokeWidth={on ? 2.2 : 1.8} />
                    <span className="max-lg:hidden">{it.label}</span>
                  </a>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-line px-2.5 py-3">
          <a href="#/ayarlar" title="Ayarlar" className={cn('flex items-center gap-2.5 rounded-[var(--radius-panel)] px-2.5 py-2 text-[13.5px] max-lg:justify-center',
            page === 'ayarlar' ? 'bg-brand-soft font-semibold text-brand-ink' : 'text-ink-2 hover:bg-surface-2 hover:text-ink')}>
            <Settings className="size-[18px]" /> <span className="max-lg:hidden">Ayarlar</span>
          </a>
          <div className="mt-1 flex items-center gap-1 max-lg:flex-col">
            <button onClick={() => setDark(!dark)} title={dark ? 'Açık tema' : 'Koyu tema'}
              className="flex flex-1 items-center gap-2.5 rounded-[var(--radius-panel)] px-2.5 py-2 text-[13.5px] text-ink-2 hover:bg-surface-2 hover:text-ink max-lg:justify-center">
              {dark ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
              <span className="max-lg:hidden">{dark ? 'Açık tema' : 'Koyu tema'}</span>
            </button>
            <button onClick={onLogout} title="Çıkış yap" aria-label="Çıkış yap"
              className="flex items-center rounded-[var(--radius-panel)] px-2.5 py-2 text-ink-2 hover:bg-surface-2 hover:text-neg">
              <LogOut className="size-[18px]" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="no-print sticky top-0 z-30 flex items-center gap-x-4 gap-y-2 border-b border-line bg-canvas/90 px-6 py-2.5 max-sm:px-3 backdrop-blur max-md:flex-wrap">
          {!DONEMSIZ.has(page) && <>
            <PeriodStrip />
            <Segmented<Currency> value={currency} onChange={setCurrency} options={[
              { value: 'TL', label: '₺ TL', title: 'Tutarlar Türk lirası' },
              { value: 'USD', label: '$ USD', title: 'Tutarlar işlem günündeki kurla USD' },
              { value: 'BOTH', label: 'İkisi', title: 'TL ve USD yan yana' },
            ]} />
            <SyncButton />
          </>}
          <a href="#/studyo" className="ml-auto flex h-[52px] shrink-0 items-center pl-2 max-md:h-9" aria-label={`${PRODUCT} ana sayfa`}>
            <span className="max-xl:hidden"><TailglassLogo size={30} /></span>
            <span className="xl:hidden"><TailglassLogo size={32} compact /></span>
          </a>
        </div>
        <main className="scroll-thin min-w-0 flex-1 overflow-y-auto px-6 pt-6 max-sm:px-3 pb-16">{children}</main>
      </div>
    </div>
  )
}

function SyncButton() {
  const { meta, reloadMeta } = useWork()
  const [running, setRunning] = useState(false)
  const [step, setStep] = useState<string | null>(null)
  const last = meta?.data.last_sync

  const start = async () => {
    try {
      await api.post('/api/sync/baslat')
      setRunning(true)
    } catch (e) {
      toast.err(e instanceof Error ? e.message : 'Senkron başlatılamadı.')
    }
  }

  useEffect(() => {
    if (!running) return
    const t = setInterval(async () => {
      const d = await api.get<{ running: boolean; step: string | null; result: { success: boolean; message: string } | null }>('/api/sync/durum')
      setStep(d.step)
      if (!d.running) {
        setRunning(false)
        clearInterval(t)
        if (d.result) (d.result.success ? toast.ok : toast.err)(d.result.message)
        await reloadMeta()
        window.dispatchEvent(new Event('defter:sync'))
      }
    }, 1200)
    return () => clearInterval(t)
  }, [running, reloadMeta])

  const kaynak = meta?.settings?.logo_source === 'demo' ? 'Demo veri' : 'Logo'
  return (
    <button onClick={start} disabled={running}
      title={last ? `${kaynak} — son senkron ${last.finished_at?.replace('T', ' ')}` : 'Henüz senkron yapılmadı'}
      className="flex h-10 shrink-0 items-center gap-2 rounded-[var(--radius-ctl)] border border-line-strong bg-surface px-3 text-left hover:border-ink-2 disabled:opacity-80">
      <RefreshCw className={cn('size-4 text-ink-2', running && 'animate-spin')} />
      <span className="flex flex-col leading-tight max-xl:hidden">
        <span className="text-[11px] text-muted">{kaynak}</span>
        <span className="text-[12.5px] font-medium whitespace-nowrap text-ink">
          {running ? (step || 'Senkronize ediliyor') : last ? `${last.finished_at?.slice(8, 10)}.${last.finished_at?.slice(5, 7)} ${last.finished_at?.slice(11, 16)} itibarıyla` : 'Senkronize et'}
        </span>
      </span>
    </button>
  )
}

export function PageHeader({ title, subtitle, actions, children }: {
  title: string; subtitle?: ReactNode; actions?: ReactNode; children?: ReactNode
}) {
  return (
    <header className="mb-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="display text-[30px] leading-tight font-semibold text-ink">{title}</h1>
          {subtitle && <p className="mt-1 max-w-3xl text-[13.5px] text-ink-2">{subtitle}</p>}
        </div>
        {actions && <div className="no-print flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
      {children && <div className="no-print mt-4">{children}</div>}
    </header>
  )
}

export const go = navigate
