import { useEffect, useMemo, useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getOffers, getSales, type Offer, type Sale } from '@/lib/api'
import { isExpiringSoon } from '@/lib/licenseAnalytics'

type Status = 'loading' | 'error' | 'ready'

const UNKNOWN_REP = '(Bilinmeyen)'

interface RepStats {
  rep: string
  activeLicenses: number
  expiringSoon: number
  openOffers: number
  wonOffers: number
  lostOffers: number
}

function buildRepStats(sales: Sale[], offers: Offer[]): RepStats[] {
  const reps = new Map<string, RepStats>()

  function get(rep: string) {
    const key = rep.trim() || UNKNOWN_REP
    let stats = reps.get(key)
    if (!stats) {
      stats = { rep: key, activeLicenses: 0, expiringSoon: 0, openOffers: 0, wonOffers: 0, lostOffers: 0 }
      reps.set(key, stats)
    }
    return stats
  }

  for (const s of sales) {
    if (s.status === 'EXPIRED' || s.status === 'NEEDS_DURATION') continue
    const stats = get(s.sales_rep ?? '')
    stats.activeLicenses += 1
    if (isExpiringSoon(s)) stats.expiringSoon += 1
  }

  for (const o of offers) {
    const stats = get(o.sales_rep ?? '')
    if (o.status === 'PENDING') stats.openOffers += 1
    else if (o.status === 'ACCEPTED') stats.wonOffers += 1
    else if (o.status === 'REJECTED') stats.lostOffers += 1
  }

  return [...reps.values()].sort((a, b) => {
    if (a.rep === UNKNOWN_REP) return 1
    if (b.rep === UNKNOWN_REP) return -1
    return a.rep.localeCompare(b.rep, 'tr')
  })
}

export function RepsTab() {
  const [sales, setSales] = useState<Sale[]>([])
  const [offers, setOffers] = useState<Offer[]>([])
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const [salesData, offersData] = await Promise.all([getSales(), getOffers()])
    if (salesData && offersData) {
      setSales(salesData)
      setOffers(offersData)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const stats = useMemo(() => buildRepStats(sales, offers), [sales, offers])

  if (status === 'loading') {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-32 animate-pulse rounded-2xl bg-black/5 dark:bg-white/5" />
        ))}
      </div>
    )
  }

  if (status === 'error') {
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
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {stats.map((s) => {
        const decided = s.wonOffers + s.lostOffers
        const winRate = decided > 0 ? Math.round((s.wonOffers / decided) * 100) : null
        return (
          <Card key={s.rep} className="p-5">
            <h3 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">{s.rep}</h3>
            <div className="grid grid-cols-2 gap-3 text-center">
              <Stat value={s.activeLicenses} label="Aktif Lisans" />
              <Stat value={s.expiringSoon} label="Yakında Dolacak" tone={s.expiringSoon > 0 ? 'warn' : 'default'} />
              <Stat value={s.openOffers} label="Açık Teklif" />
              <Stat
                value={winRate !== null ? `%${winRate}` : '-'}
                label={`Kazanma Oranı (${s.wonOffers}/${decided})`}
              />
            </div>
          </Card>
        )
      })}
    </div>
  )
}

function Stat({ value, label, tone = 'default' }: { value: number | string; label: string; tone?: 'default' | 'warn' }) {
  return (
    <div className="rounded-xl bg-black/[0.03] p-3 dark:bg-white/[0.05]">
      <p
        className={
          tone === 'warn' && Number(value) > 0
            ? 'text-lg font-semibold text-amber-600 dark:text-amber-400'
            : 'text-lg font-semibold text-black/90 dark:text-white'
        }
      >
        {value}
      </p>
      <p className="text-xs text-black/50 dark:text-white/50">{label}</p>
    </div>
  )
}
