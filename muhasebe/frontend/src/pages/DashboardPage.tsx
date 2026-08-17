import { useState } from 'react'
import { Sidebar, type DashboardTab } from '@/components/dashboard/Sidebar'
import { OverviewTab } from '@/components/dashboard/OverviewTab'
import { LicensesTab } from '@/components/dashboard/LicensesTab'
import { SubscriptionsTab } from '@/components/dashboard/SubscriptionsTab'
import { ProductsTab } from '@/components/dashboard/ProductsTab'
import { OffersTab } from '@/components/dashboard/OffersTab'
import { RepsTab } from '@/components/dashboard/RepsTab'

interface DashboardPageProps {
  onLogout: () => void
}

const TITLES: Record<DashboardTab, string> = {
  overview: 'Özet',
  licenses: 'Lisanslar',
  subscriptions: 'Abonelikler',
  products: 'Ürünler',
  offers: 'Teklifler',
  reps: 'Temsilciler',
}

export function DashboardPage({ onLogout }: DashboardPageProps) {
  const [tab, setTab] = useState<DashboardTab>('overview')

  return (
    <div className="flex h-screen overflow-hidden bg-bg dark:bg-neutral-950">
      <Sidebar active={tab} onSelect={setTab} onLogout={onLogout} />
      <main className="flex-1 overflow-y-auto px-8 py-8">
        <h1 className="font-display mb-6 text-3xl italic text-black/90 dark:text-white">{TITLES[tab]}</h1>
        {tab === 'overview' && <OverviewTab />}
        {tab === 'licenses' && <LicensesTab />}
        {tab === 'subscriptions' && <SubscriptionsTab />}
        {tab === 'products' && <ProductsTab />}
        {tab === 'offers' && <OffersTab />}
        {tab === 'reps' && <RepsTab />}
      </main>
    </div>
  )
}
