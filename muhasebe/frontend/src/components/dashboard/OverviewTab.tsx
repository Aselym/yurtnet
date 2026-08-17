import { useEffect, useState } from 'react'
import { AlertTriangle, BadgeCheck, Clock, Mail, Package, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { StatCard } from './StatCard'
import { MonthlyExpiryChart, StatusBarChart } from './AnalyticsCharts'
import { ReminderModal } from './ReminderModal'
import { RenewalsPanel } from './RenewalsPanel'
import { getSales, getStats, type Sale, type StatsResponse } from '@/lib/api'
import {
  EXPIRING_SOON_DAYS,
  getBrandStats,
  getExpiringSoon,
  getLostCustomers,
  getRevenueForecast,
} from '@/lib/licenseAnalytics'

type Status = 'loading' | 'error' | 'ready'

export function OverviewTab() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [reminderSale, setReminderSale] = useState<Sale | null>(null)

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
  const lostCustomers = getLostCustomers(sales)
  const brandStats = getBrandStats(sales)
  const revenueForecast = getRevenueForecast(sales)
  const totalForecast = revenueForecast.reduce((sum, b) => sum + b.revenue, 0)
  const totalMissingPrice = revenueForecast.reduce((sum, b) => sum + b.missingPrice, 0)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Toplam Satış" value={stats.total_sales} icon={Package} />
        <StatCard label="Aktif Lisans" value={stats.active_licenses} icon={BadgeCheck} />
        <StatCard label="Yakında Dolacak" value={stats.expiring_soon} icon={Clock} tone="warn" />
        <StatCard label="Gönderilen Hatırlatma" value={stats.reminders_sent} icon={Mail} />
        <StatCard label="Süresi Dolmuş" value={stats.expired_licenses} icon={XCircle} tone="danger" />
      </div>

      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">
          Beklenen Yenileme Geliri (Önümüzdeki 3 Ay)
        </h3>
        <p className="mb-4 text-2xl font-semibold text-black/90 dark:text-white">
          {totalForecast.toLocaleString('tr-TR')} TRY
        </p>
        <div className="grid grid-cols-3 gap-3">
          {revenueForecast.map((b) => (
            <div key={b.key} className="rounded-xl bg-black/[0.03] p-3 text-center dark:bg-white/[0.05]">
              <p className="text-base font-semibold text-black/90 dark:text-white">
                {b.revenue.toLocaleString('tr-TR')} TRY
              </p>
              <p className="text-xs text-black/50 dark:text-white/50">{b.label}</p>
            </div>
          ))}
        </div>
        {totalMissingPrice > 0 && (
          <p className="mt-3 text-xs text-black/40 dark:text-white/40">
            {totalMissingPrice} kayıtta fiyat bilgisi yok, toplama dahil edilmedi.
          </p>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <StatusBarChart sales={sales} />
        <MonthlyExpiryChart sales={sales} />
      </div>

      <Card className="p-5">
        <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">Marka Performansı</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-black/5 text-xs uppercase tracking-wide text-black/40 dark:border-white/10 dark:text-white/40">
                <th className="px-3 py-2 font-medium">Marka</th>
                <th className="px-3 py-2 font-medium">Aktif</th>
                <th className="px-3 py-2 font-medium">Süresi Dolmuş</th>
                <th className="px-3 py-2 font-medium">Yenileme Oranı</th>
              </tr>
            </thead>
            <tbody>
              {brandStats.map((b) => (
                <tr key={b.brand} className="border-b border-black/5 last:border-0 dark:border-white/5">
                  <td className="px-3 py-2 font-medium text-black/80 dark:text-white/80">{b.brand}</td>
                  <td className="px-3 py-2 text-black/80 dark:text-white/80">{b.active}</td>
                  <td className="px-3 py-2 text-black/80 dark:text-white/80">{b.expired}</td>
                  <td className="px-3 py-2 text-black/80 dark:text-white/80">
                    {b.renewalRate !== null ? `%${b.renewalRate} (${b.renewed}/${b.expired})` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

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
                  <th className="px-3 py-2 font-medium" />
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
                    <td className="px-3 py-2">
                      <button
                        onClick={() => setReminderSale(s)}
                        title="Müşteriye Mail Gönder"
                        className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
                      >
                        <Mail className="h-4 w-4" strokeWidth={1.75} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <RenewalsPanel />

      {lostCustomers.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">
            Kayıp Müşteriler ({lostCustomers.length})
          </h3>
          <p className="mb-4 text-xs text-black/40 dark:text-white/40">
            Süresi dolmuş ve yenilendiğine dair bir kayıt bulunamayan lisanslar — satış ekibinin araması gerekebilir.
          </p>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-black/5 text-xs uppercase tracking-wide text-black/40 dark:border-white/10 dark:text-white/40">
                  <th className="px-3 py-2 font-medium">Müşteri</th>
                  <th className="px-3 py-2 font-medium">Ürün</th>
                  <th className="px-3 py-2 font-medium">Süresi Dolduğu Tarih</th>
                </tr>
              </thead>
              <tbody>
                {lostCustomers.map((s) => (
                  <tr key={s.id} className="border-b border-black/5 last:border-0 dark:border-white/5">
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.client_name}</td>
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.product_name}</td>
                    <td className="px-3 py-2 text-black/80 dark:text-white/80">{s.expiration_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

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
    </div>
  )
}
