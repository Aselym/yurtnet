import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Clock, FileText, Mail } from 'lucide-react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { ReminderModal } from './ReminderModal'
import { SetDurationModal } from './SetDurationModal'
import { CustomerProfileModal } from './CustomerProfileModal'
import { NewOfferModal } from './NewOfferModal'
import { getSales, type Sale } from '@/lib/api'
import { EXPIRING_SOON_DAYS, isExpiringSoon, isStaleExpired } from '@/lib/licenseAnalytics'

type Status = 'loading' | 'error' | 'ready'

export function LicensesTab() {
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')
  const [reminderSale, setReminderSale] = useState<Sale | null>(null)
  const [durationSale, setDurationSale] = useState<Sale | null>(null)
  const [showStale, setShowStale] = useState(false)
  const [profileClient, setProfileClient] = useState<string | null>(null)
  const [offerSale, setOfferSale] = useState<Sale | null>(null)

  async function load() {
    setStatus('loading')
    const data = await getSales()
    if (data) {
      setSales(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  const staleCount = useMemo(() => sales.filter(isStaleExpired).length, [sales])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return sales.filter((s) => {
      if (!showStale && isStaleExpired(s)) return false
      if (!q) return true
      return s.client_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q)
    })
  }, [sales, search, showStale])

  const columns: DataTableColumn<Sale>[] = [
    { key: 'product', header: 'Ürün', render: (s) => s.product_name },
    {
      key: 'expiration',
      header: 'Bitiş Tarihi',
      render: (s) =>
        isExpiringSoon(s) ? (
          <span className="inline-flex items-center gap-1.5 text-red-600 dark:text-red-400">
            <AlertTriangle className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-label={`${EXPIRING_SOON_DAYS} gün içinde doluyor`} />
            {s.expiration_date}
          </span>
        ) : (
          s.expiration_date
        ),
    },
    { key: 'days_left', header: 'Kalan Gün', render: (s) => (s.days_left >= 0 ? `${s.days_left} gün` : '-') },
    { key: 'status', header: 'Durum', render: (s) => <StatusPill status={s.status} /> },
    {
      key: 'actions',
      header: '',
      render: (s) =>
        s.status === 'NEEDS_DURATION' ? (
          <button
            onClick={() => setDurationSale(s)}
            title="Süre Girin"
            className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
          >
            <Clock className="h-4 w-4" strokeWidth={1.75} />
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setReminderSale(s)}
              title="Müşteriye Mail Gönder"
              className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
            >
              <Mail className="h-4 w-4" strokeWidth={1.75} />
            </button>
            {(s.status === 'EXPIRED' || isExpiringSoon(s)) && (
              <button
                onClick={() => setOfferSale(s)}
                title="Yenileme Teklifi Oluştur"
                className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
              >
                <FileText className="h-4 w-4" strokeWidth={1.75} />
              </button>
            )}
          </div>
        ),
    },
  ]

  return (
    <>
      {staleCount > 0 && (
        <label className="mb-3 flex w-fit items-center gap-2 text-sm text-black/50 dark:text-white/50">
          <input type="checkbox" checked={showStale} onChange={(e) => setShowStale(e.target.checked)} />
          2024'te süresi dolmuş eski kayıtları göster ({staleCount})
        </label>
      )}
      <DataTable
        columns={columns}
        rows={filtered}
        status={status}
        onRetry={load}
        searchPlaceholder="Müşteri veya ürün ara..."
        searchValue={search}
        onSearchChange={setSearch}
        getRowKey={(s) => s.id}
        emptyMessage="Henüz lisans kaydı yok."
        groupBy={(s) => s.client_name}
        onGroupClick={setProfileClient}
      />
      {profileClient && <CustomerProfileModal clientName={profileClient} onClose={() => setProfileClient(null)} />}
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
      {durationSale && (
        <SetDurationModal
          saleId={durationSale.id}
          clientName={durationSale.client_name}
          productName={durationSale.product_name}
          onClose={() => setDurationSale(null)}
          onSaved={load}
        />
      )}
      {offerSale && (
        <NewOfferModal
          onClose={() => setOfferSale(null)}
          onCreated={() => {}}
          initial={{
            client_name: offerSale.client_name,
            product_name: offerSale.product_name,
            notes: `Yenileme teklifi — eski bitiş tarihi: ${offerSale.expiration_date}`,
          }}
        />
      )}
    </>
  )
}
