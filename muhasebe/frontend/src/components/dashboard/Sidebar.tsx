import { FileText, KeyRound, LayoutGrid, LogOut, Package, RefreshCcw, Users, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'

export type DashboardTab = 'overview' | 'licenses' | 'subscriptions' | 'products' | 'offers' | 'reps'

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
  { id: 'reps', label: 'Temsilciler', icon: Users },
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
                ? 'bg-brand-soft text-brand-dark dark:bg-brand/15 dark:text-brand'
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
