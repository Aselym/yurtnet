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
