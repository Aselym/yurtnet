import { useEffect, useState } from 'react'
import { Check, X } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { confirmRenewal, getRenewals, type RenewalCandidate } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function RenewalsPanel() {
  const [candidates, setCandidates] = useState<RenewalCandidate[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [busyId, setBusyId] = useState<number | null>(null)

  async function load() {
    setStatus('loading')
    const data = await getRenewals()
    if (data) {
      setCandidates(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleDecision(eskiId: number, karar: 'CONFIRMED' | 'REJECTED') {
    setBusyId(eskiId)
    const result = await confirmRenewal(eskiId, karar)
    if (result.success) {
      setCandidates((prev) => prev.filter((c) => c.eski_id !== eskiId))
    }
    setBusyId(null)
  }

  if (status === 'loading') return null
  if (status === 'error' || candidates.length === 0) return null

  return (
    <Card className="p-5">
      <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">
        Yenileme Adayları ({candidates.length})
      </h3>
      <p className="mb-4 text-xs text-black/40 dark:text-white/40">
        Sistem, süresi dolmuş bir lisansla aynı müşteri ve kategoride daha yeni bir satış buldu. Bu gerçekten aynı
        lisansın yenilenmesi mi?
      </p>
      <div className="space-y-2">
        {candidates.map((c) => (
          <div
            key={c.eski_id}
            className="flex flex-col gap-2 rounded-xl border border-black/5 p-3 text-sm sm:flex-row sm:items-center sm:justify-between dark:border-white/10"
          >
            <div>
              <p className="font-medium text-black/80 dark:text-white/80">{c.musteri}</p>
              <p className="text-xs text-black/50 dark:text-white/50">
                {c.eski_urun} ({c.eski_bitis}) → {c.yeni_urun} ({c.yeni_satis})
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                onClick={() => handleDecision(c.eski_id, 'CONFIRMED')}
                disabled={busyId === c.eski_id}
                title="Yenilendi, onayla"
                className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-emerald-50 hover:text-emerald-600 disabled:opacity-50 dark:text-white/40 dark:hover:bg-emerald-500/10 dark:hover:text-emerald-400"
              >
                <Check className="h-4 w-4" strokeWidth={2} />
              </button>
              <button
                onClick={() => handleDecision(c.eski_id, 'REJECTED')}
                disabled={busyId === c.eski_id}
                title="Yanlış eşleşme, reddet"
                className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:text-white/40 dark:hover:bg-red-500/10 dark:hover:text-red-400"
              >
                <X className="h-4 w-4" strokeWidth={2} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
