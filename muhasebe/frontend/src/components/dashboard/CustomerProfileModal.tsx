import { useEffect, useState, type ReactNode } from 'react'
import { Mail, MapPin, Phone } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { StatusPill } from './StatusPill'
import {
  getOffers,
  getProducts,
  getSales,
  getSubscriptions,
  type Offer,
  type Product,
  type Sale,
  type Subscription,
} from '@/lib/api'

interface CustomerProfileModalProps {
  clientName: string
  onClose: () => void
}

type Status = 'loading' | 'error' | 'ready'

export function CustomerProfileModal({ clientName, onClose }: CustomerProfileModalProps) {
  const [status, setStatus] = useState<Status>('loading')
  const [sales, setSales] = useState<Sale[]>([])
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [offers, setOffers] = useState<Offer[]>([])

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    Promise.all([getSales(), getSubscriptions(), getProducts(), getOffers()]).then((results) => {
      if (cancelled) return
      const [salesData, subsData, productsData, offersData] = results
      if (salesData && subsData && productsData && offersData) {
        setSales(salesData.filter((s) => s.client_name === clientName))
        setSubscriptions(subsData.filter((s) => s.client_name === clientName))
        setProducts(productsData.filter((p) => p.client_name === clientName))
        setOffers(offersData.filter((o) => o.client_name === clientName))
        setStatus('ready')
      } else {
        setStatus('error')
      }
    })
    return () => {
      cancelled = true
    }
  }, [clientName])

  const activeLicenses = sales.filter((s) => s.status !== 'EXPIRED' && s.status !== 'NEEDS_DURATION').length
  const totalSpent = products.reduce((sum, p) => sum + (p.line_total ?? 0), 0)
  const openOffers = offers.filter((o) => o.status === 'PENDING').length

  // Iletisim bilgisi her satista ayni musteriye ait tekrarlaniyor; ilk dolu
  // kaydi almak yeterli. Logo'daki CLCARD'dan geliyor (bkz. logo_sync.py).
  const contactSource = [...sales, ...products, ...subscriptions]
  const email = contactSource.find((r) => r.client_email)?.client_email
  const phone = contactSource.find((r) => r.client_phone)?.client_phone
  const city = contactSource.find((r) => r.client_city)?.client_city

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="max-h-[85vh] w-full max-w-2xl overflow-y-auto p-6">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-black/90 dark:text-white">{clientName}</h2>
            {status === 'ready' && (email || phone || city) && (
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-black/50 dark:text-white/50">
                {email && (
                  <span className="flex items-center gap-1.5">
                    <Mail className="h-3.5 w-3.5" strokeWidth={1.75} />
                    {email}
                  </span>
                )}
                {phone && (
                  <span className="flex items-center gap-1.5">
                    <Phone className="h-3.5 w-3.5" strokeWidth={1.75} />
                    {phone}
                  </span>
                )}
                {city && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="h-3.5 w-3.5" strokeWidth={1.75} />
                    {city}
                  </span>
                )}
              </div>
            )}
          </div>
          <Button variant="ghost" onClick={onClose} className="h-8 px-3 shrink-0">
            Kapat
          </Button>
        </div>

        {status === 'loading' && <p className="text-sm text-black/50 dark:text-white/50">Yükleniyor...</p>}
        {status === 'error' && <p className="text-sm text-red-600 dark:text-red-400">Veriler yüklenemedi.</p>}

        {status === 'ready' && (
          <div className="space-y-6">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-xl bg-black/[0.03] p-3 dark:bg-white/[0.05]">
                <p className="text-lg font-semibold text-black/90 dark:text-white">{activeLicenses}</p>
                <p className="text-xs text-black/50 dark:text-white/50">Aktif Lisans</p>
              </div>
              <div className="rounded-xl bg-black/[0.03] p-3 dark:bg-white/[0.05]">
                <p className="text-lg font-semibold text-black/90 dark:text-white">
                  {totalSpent.toLocaleString('tr-TR')} TRY
                </p>
                <p className="text-xs text-black/50 dark:text-white/50">Toplam Ürün Harcaması</p>
              </div>
              <div className="rounded-xl bg-black/[0.03] p-3 dark:bg-white/[0.05]">
                <p className="text-lg font-semibold text-black/90 dark:text-white">{openOffers}</p>
                <p className="text-xs text-black/50 dark:text-white/50">Açık Teklif</p>
              </div>
            </div>

            <Section title={`Lisanslar (${sales.length})`} empty="Lisans kaydı yok.">
              {sales.map((s) => (
                <Row key={s.id} left={s.product_name} right={<StatusPill status={s.status} />} sub={s.expiration_date} />
              ))}
            </Section>

            <Section title={`Abonelikler (${subscriptions.length})`} empty="Abonelik kaydı yok.">
              {subscriptions.map((s) => (
                <Row
                  key={s.id}
                  left={s.product_name}
                  right={<StatusPill status={s.status} />}
                  sub={s.days_since_last != null ? `Son faturadan bu yana ${s.days_since_last} gün` : undefined}
                />
              ))}
            </Section>

            <Section title={`Ürünler (${products.length})`} empty="Ürün kaydı yok.">
              {products.map((p) => (
                <Row
                  key={p.id}
                  left={`${p.product_name} × ${p.quantity}`}
                  right={p.line_total != null ? `${p.line_total.toLocaleString('tr-TR')} ${p.currency}` : '-'}
                  sub={p.sale_date}
                />
              ))}
            </Section>

            <Section title={`Teklifler (${offers.length})`} empty="Teklif kaydı yok.">
              {offers.map((o) => (
                <Row
                  key={o.id}
                  left={o.product_name}
                  right={<StatusPill status={o.status} />}
                  sub={o.offer_price ? `${o.offer_price.toLocaleString('tr-TR')} ${o.currency}` : undefined}
                />
              ))}
            </Section>
          </div>
        )}
      </Card>
    </div>
  )
}

function Section({ title, empty, children }: { title: string; empty: string; children: ReactNode }) {
  const hasChildren = Array.isArray(children) ? children.length > 0 : Boolean(children)
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-black/40 dark:text-white/40">{title}</h3>
      {hasChildren ? (
        <div className="max-h-48 space-y-1 overflow-y-auto rounded-xl border border-black/5 p-2 dark:border-white/10">
          {children}
        </div>
      ) : (
        <p className="text-sm text-black/40 dark:text-white/40">{empty}</p>
      )}
    </div>
  )
}

function Row({ left, right, sub }: { left: string; right: ReactNode; sub?: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm">
      <div className="min-w-0">
        <p className="truncate text-black/80 dark:text-white/80">{left}</p>
        {sub && <p className="text-xs text-black/40 dark:text-white/40">{sub}</p>}
      </div>
      <div className="shrink-0 text-black/60 dark:text-white/60">{right}</div>
    </div>
  )
}
