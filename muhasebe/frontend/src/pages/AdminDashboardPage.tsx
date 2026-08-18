import { useEffect, useState } from 'react'
import { AlertTriangle, BadgeCheck, Clock, LogOut, Percent, TrendingUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StatCard } from '@/components/dashboard/StatCard'
import { StatusBarChart } from '@/components/dashboard/AnalyticsCharts'
import {
  OfferFunnelChart,
  RankedBarChart,
  RevenueTrendChart,
  SubscriptionHealthDonut,
} from '@/components/admin/AdminCharts'
import { InsightsPanel } from '@/components/admin/InsightsPanel'
import {
  getOffers,
  getSales,
  getStats,
  getSubscriptions,
  type Offer,
  type Sale,
  type StatsResponse,
  type Subscription,
} from '@/lib/api'
import { getBrandStats, getLostCustomers, getRevenueForecast } from '@/lib/licenseAnalytics'
import { UNKNOWN_REP, getOfferFunnel, getRepPerformance } from '@/lib/adminAnalytics'

interface AdminDashboardPageProps {
  onLogout: () => void
}

type Status = 'loading' | 'error' | 'ready'

export function AdminDashboardPage({ onLogout }: AdminDashboardPageProps) {
  const [sales, setSales] = useState<Sale[]>([])
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [offers, setOffers] = useState<Offer[]>([])
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const [salesData, subsData, offersData, statsData] = await Promise.all([
      getSales(),
      getSubscriptions(),
      getOffers(),
      getStats(),
    ])
    if (salesData && subsData && offersData && statsData) {
      setSales(salesData)
      setSubscriptions(subsData)
      setOffers(offersData)
      setStats(statsData)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="min-h-screen bg-bg dark:bg-neutral-950">
      <header className="flex items-center justify-between border-b border-black/5 bg-white/60 px-8 py-5 backdrop-blur-md dark:border-white/10 dark:bg-white/[0.03]">
        <div className="flex items-center gap-4">
          <img src="/static/images/logo.png" alt="Piramit Bilgisayar" className="h-8 dark:hidden" />
          <img src="/static/images/logo-dark.png" alt="Piramit Bilgisayar" className="hidden h-8 dark:block" />
          <span className="h-6 w-px bg-black/10 dark:bg-white/10" />
          <h1 className="font-display text-2xl italic text-black/90 dark:text-white">Yönetici Özeti</h1>
        </div>
        <Button variant="ghost" onClick={onLogout}>
          <LogOut className="h-4 w-4" strokeWidth={1.75} />
          Çıkış Yap
        </Button>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-8 py-8">
        {status === 'loading' && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse rounded-2xl bg-black/5 dark:bg-white/5" />
            ))}
          </div>
        )}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-black/5 p-10 text-center dark:border-white/10">
            <p className="text-sm text-black/50 dark:text-white/50">Veriler yüklenemedi.</p>
            <Button variant="ghost" onClick={load}>
              Tekrar dene
            </Button>
          </div>
        )}

        {status === 'ready' && stats && (
          <AdminDashboardContent sales={sales} subscriptions={subscriptions} offers={offers} stats={stats} />
        )}
      </main>
    </div>
  )
}

interface AdminDashboardContentProps {
  sales: Sale[]
  subscriptions: Subscription[]
  offers: Offer[]
  stats: StatsResponse
}

function AdminDashboardContent({ sales, subscriptions, offers, stats }: AdminDashboardContentProps) {
  const revenueForecast = getRevenueForecast(sales, 3)
  const totalForecast = revenueForecast.reduce((sum, b) => sum + b.revenue, 0)

  const lostCustomers = getLostCustomers(sales)
  const revenueAtRisk = lostCustomers.reduce((sum, s) => sum + (s.price ?? 0), 0)

  const funnel = getOfferFunnel(offers)

  const brandStats = getBrandStats(sales)
  const repPerformance = getRepPerformance(sales, offers)
    .filter((r) => r.rep !== UNKNOWN_REP)
    .sort((a, b) => b.activeLicenses - a.activeLicenses)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Aktif Lisans" value={stats.active_licenses} icon={BadgeCheck} />
        <StatCard label="Yakında Dolacak" value={stats.expiring_soon} icon={Clock} tone="warn" />
        <StatCard
          label="Önümüzdeki 3 Ay Beklenen Gelir"
          value={`${totalForecast.toLocaleString('tr-TR')} TRY`}
          icon={TrendingUp}
        />
        <StatCard
          label="Risk Altındaki Gelir"
          value={`${revenueAtRisk.toLocaleString('tr-TR')} TRY`}
          icon={AlertTriangle}
          tone="danger"
        />
        <StatCard
          label="Teklif Kazanma Oranı"
          value={funnel.winRate !== null ? `%${funnel.winRate}` : '-'}
          icon={Percent}
        />
      </div>

      <RevenueTrendChart sales={sales} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StatusBarChart sales={sales} />
        <SubscriptionHealthDonut subscriptions={subscriptions} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RankedBarChart
          title="Marka Performansı"
          data={brandStats.map((b) => ({
            label: b.brand,
            value: b.active + b.expired,
            sublabel: `Aktif ${b.active} · Süresi Dolmuş ${b.expired}${
              b.renewalRate !== null ? ` · Yenileme %${b.renewalRate}` : ''
            }`,
          }))}
          emptyMessage="Henüz marka bazlı lisans verisi yok."
        />
        <RankedBarChart
          title="Temsilci Performansı"
          data={repPerformance.map((r) => {
            const decided = r.wonOffers + r.lostOffers
            const winRate = decided > 0 ? Math.round((r.wonOffers / decided) * 100) : null
            return {
              label: r.rep,
              value: r.activeLicenses,
              sublabel: `Kazanma oranı ${winRate !== null ? `%${winRate}` : '-'} · ${r.expiringSoon} yakında dolacak`,
            }
          })}
          emptyMessage="Henüz temsilci bazlı veri yok."
        />
      </div>

      <OfferFunnelChart offers={offers} />

      <InsightsPanel sales={sales} subscriptions={subscriptions} offers={offers} />
    </div>
  )
}
