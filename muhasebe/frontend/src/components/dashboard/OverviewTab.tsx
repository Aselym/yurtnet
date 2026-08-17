import { useEffect, useState } from 'react'
import { AlertTriangle, BadgeCheck, Clock, Mail, Package, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { StatCard } from './StatCard'
import { MonthlyExpiryChart, StatusBarChart } from './AnalyticsCharts'
import { getSales, getStats, type Sale, type StatsResponse } from '@/lib/api'
import { EXPIRING_SOON_DAYS, getExpiringSoon } from '@/lib/licenseAnalytics'

type Status = 'loading' | 'error' | 'ready'

export function OverviewTab() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const [statsData, salesData] = await Promise.all([getStats(), getSales()])
    if (statsData && salesData) {
      setStats(statsData)
      setSales(salesData)
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

  const expiringSoon = getExpiringSoon(sales)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Toplam Satış" value={stats.total_sales} icon={Package} />
        <StatCard label="Aktif Lisans" value={stats.active_licenses} icon={BadgeCheck} />
        <StatCard label="Yakında Dolacak" value={stats.expiring_soon} icon={Clock} tone="warn" />
        <StatCard label="Gönderilen Hatırlatma" value={stats.reminders_sent} icon={Mail} />
        <StatCard label="Süresi Dolmuş" value={stats.expired_licenses} icon={XCircle} tone="danger" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StatusBarChart sales={sales} />
        <MonthlyExpiryChart sales={sales} />
      </div>

      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">
          Son {EXPIRING_SOON_DAYS} Gün İçinde Süresi Dolacaklar ({expiringSoon.length})
        </h3>
        {expiringSoon.length === 0 ? (
          <p className="text-sm text-black/50 dark:text-white/50">
            Önümüzdeki {EXPIRING_SOON_DAYS} gün içinde süresi dolacak lisans yok.
          </p>
        ) : (
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-black/5 text-xs uppercase tracking-wide text-black/40 dark:border-white/10 dark:text-white/40">
                  <th className="px-3 py-2 font-medium">Müşteri</th>
                  <th className="px-3 py-2 font-medium">Ürün</th>
                  <th className="px-3 py-2 font-medium">Bitiş Tarihi</th>
                  <th className="px-3 py-2 font-medium">Kalan Gün</th>
                </tr>
              </thead>
              <tbody>
                {expiringSoon.map((s) => (
                  <tr key={s.id} className="border-b border-black/5 last:border-0 dark:border-white/5">
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.client_name}</td>
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.product_name}</td>
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.expiration_date}</td>
                    <td className="px-3 py-2">
                      <span
                        className={
                          s.days_left <= 30
                            ? 'inline-flex items-center gap-1.5 font-medium text-red-600 dark:text-red-400'
                            : 'text-black/80 dark:text-white/80'
                        }
                      >
                        {s.days_left <= 30 && <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.75} />}
                        {s.days_left} gün
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
