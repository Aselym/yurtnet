import { useEffect, useMemo, useState } from 'react'
import { Clock, Mail } from 'lucide-react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { ReminderModal } from './ReminderModal'
import { SetDurationModal } from './SetDurationModal'
import { getSales, type Sale } from '@/lib/api'

type Status = 'loading' | 'error' | 'ready'

export function LicensesTab() {
  const [sales, setSales] = useState<Sale[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')
  const [reminderSale, setReminderSale] = useState<Sale | null>(null)
  const [durationSale, setDurationSale] = useState<Sale | null>(null)

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

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sales
    return sales.filter(
      (s) => s.client_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q)
    )
  }, [sales, search])

  const columns: DataTableColumn<Sale>[] = [
    { key: 'client', header: 'Müşteri', render: (s) => s.client_name },
    { key: 'product', header: 'Ürün', render: (s) => s.product_name },
    { key: 'expiration', header: 'Bitiş Tarihi', render: (s) => s.expiration_date },
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
          <button
            onClick={() => setReminderSale(s)}
            title="Müşteriye Mail Gönder"
            className="rounded-lg p-1.5 text-black/40 transition-colors hover:bg-brand-soft hover:text-brand-dark dark:text-white/40 dark:hover:bg-brand/15 dark:hover:text-brand"
          >
            <Mail className="h-4 w-4" strokeWidth={1.75} />
          </button>
        ),
    },
  ]

  return (
    <>
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
      />
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
    </>
  )
}
