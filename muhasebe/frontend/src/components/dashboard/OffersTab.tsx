import { useEffect, useMemo, useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { NewOfferModal } from './NewOfferModal'
import { CustomerProfileModal } from './CustomerProfileModal'
import { deleteOffer, getOffers, updateOfferStatus, type Offer } from '@/lib/api'
import { cn } from '@/lib/cn'

type LoadStatus = 'loading' | 'error' | 'ready'

const COLUMNS: { status: Offer['status']; label: string }[] = [
  { status: 'PENDING', label: 'Beklemede' },
  { status: 'ACCEPTED', label: 'Kabul Edildi' },
  { status: 'REJECTED', label: 'Reddedildi' },
]

const COLUMN_ACCENT: Record<Offer['status'], string> = {
  PENDING: 'border-t-blue-400 dark:border-t-blue-500',
  ACCEPTED: 'border-t-emerald-400 dark:border-t-emerald-500',
  REJECTED: 'border-t-red-400 dark:border-t-red-500',
}

function formatPrice(offer: Offer) {
  if (!offer.offer_price) return null
  return `${offer.offer_price.toLocaleString('tr-TR')} ${offer.currency}`
}

export function OffersTab() {
  const [offers, setOffers] = useState<Offer[]>([])
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [showNew, setShowNew] = useState(false)
  const [dragOverColumn, setDragOverColumn] = useState<Offer['status'] | null>(null)
  const [profileClient, setProfileClient] = useState<string | null>(null)

  async function load() {
    setStatus('loading')
    const data = await getOffers()
    if (data) {
      setOffers(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const byColumn = useMemo(() => {
    const grouped: Record<Offer['status'], Offer[]> = { PENDING: [], ACCEPTED: [], REJECTED: [] }
    for (const o of offers) grouped[o.status].push(o)
    return grouped
  }, [offers])

  async function handleDrop(offerId: number, newStatus: Offer['status']) {
    setDragOverColumn(null)
    const offer = offers.find((o) => o.id === offerId)
    if (!offer || offer.status === newStatus) return
    setOffers((prev) => prev.map((o) => (o.id === offerId ? { ...o, status: newStatus } : o)))
    const result = await updateOfferStatus(offerId, newStatus)
    if (!result.success) load()
  }

  async function handleDelete(offerId: number) {
    setOffers((prev) => prev.filter((o) => o.id !== offerId))
    const result = await deleteOffer(offerId)
    if (!result.success) load()
  }

  if (status === 'loading') {
    return <p className="py-24 text-center text-sm text-black/50 dark:text-white/50">Yükleniyor...</p>
  }

  if (status === 'error') {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-center">
        <p className="text-sm text-red-600 dark:text-red-400">Teklifler yüklenemedi.</p>
        <Button variant="ghost" onClick={load}>
          Tekrar Dene
        </Button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-5 flex justify-end">
        <Button onClick={() => setShowNew(true)}>
          <Plus className="h-4 w-4" strokeWidth={2} />
          Yeni Teklif
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {COLUMNS.map(({ status: colStatus, label }) => (
          <div
            key={colStatus}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOverColumn(colStatus)
            }}
            onDragLeave={() => setDragOverColumn((cur) => (cur === colStatus ? null : cur))}
            onDrop={(e) => {
              e.preventDefault()
              const offerId = Number(e.dataTransfer.getData('text/plain'))
              if (offerId) handleDrop(offerId, colStatus)
            }}
            className={cn(
              'flex min-h-[200px] flex-col gap-3 rounded-2xl border border-black/5 border-t-4 bg-black/[0.02] p-3 transition-colors dark:border-white/10 dark:bg-white/[0.02]',
              COLUMN_ACCENT[colStatus],
              dragOverColumn === colStatus && 'bg-brand-soft/60 dark:bg-brand/10'
            )}
          >
            <div className="flex items-center justify-between px-1">
              <h3 className="text-sm font-semibold text-black/70 dark:text-white/70">{label}</h3>
              <span className="text-xs text-black/40 dark:text-white/40">{byColumn[colStatus].length}</span>
            </div>

            {byColumn[colStatus].length === 0 && (
              <p className="px-1 text-xs text-black/30 dark:text-white/30">Teklif yok.</p>
            )}

            {byColumn[colStatus].map((offer) => (
              <Card
                key={offer.id}
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData('text/plain', String(offer.id))
                  e.dataTransfer.effectAllowed = 'move'
                }}
                className="group cursor-grab p-3 active:cursor-grabbing"
              >
                <div className="flex items-start justify-between gap-2">
                  <button
                    onClick={() => setProfileClient(offer.client_name)}
                    className="hover:text-brand-dark dark:hover:text-brand text-left text-sm font-medium text-black/90 hover:underline dark:text-white"
                  >
                    {offer.client_name}
                  </button>
                  <button
                    onClick={() => handleDelete(offer.id)}
                    title="Teklifi Sil"
                    className="rounded-md p-1 text-black/30 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-600 group-hover:opacity-100 dark:text-white/30 dark:hover:bg-red-500/10 dark:hover:text-red-400"
                  >
                    <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                  </button>
                </div>
                <p className="mt-0.5 text-xs text-black/50 dark:text-white/50">
                  {offer.product_name} × {offer.quantity}
                </p>
                <div className="mt-2 flex items-center justify-between text-xs text-black/40 dark:text-white/40">
                  <span>{offer.offer_date}</span>
                  {formatPrice(offer) && <span className="font-medium text-black/60 dark:text-white/60">{formatPrice(offer)}</span>}
                </div>
                {offer.sales_rep && (
                  <p className="mt-1 text-xs text-black/40 dark:text-white/40">{offer.sales_rep}</p>
                )}
                {offer.notes && (
                  <p className="mt-1.5 border-t border-black/5 pt-1.5 text-xs text-black/50 dark:border-white/10 dark:text-white/50">
                    {offer.notes}
                  </p>
                )}
              </Card>
            ))}
          </div>
        ))}
      </div>

      {showNew && (
        <NewOfferModal
          onClose={() => setShowNew(false)}
          onCreated={load}
        />
      )}
      {profileClient && <CustomerProfileModal clientName={profileClient} onClose={() => setProfileClient(null)} />}
    </div>
  )
}
