import { useEffect, useState } from 'react'
import { BadgeCheck, Clock, Mail, Package, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { StatCard } from './StatCard'
import { getStats, type StatsResponse } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function OverviewTab() {
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const data = await getStats()
    if (data) {
      setStats(data)
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

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <StatCard label="Toplam Satış" value={stats.total_sales} icon={Package} />
      <StatCard label="Aktif Lisans" value={stats.active_licenses} icon={BadgeCheck} />
      <StatCard label="Yakında Dolacak" value={stats.expiring_soon} icon={Clock} tone="warn" />
      <StatCard label="Gönderilen Hatırlatma" value={stats.reminders_sent} icon={Mail} />
      <StatCard label="Süresi Dolmuş" value={stats.expired_licenses} icon={XCircle} tone="danger" />
    </div>
  )
}
