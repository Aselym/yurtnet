import { useEffect, useMemo, useState } from 'react'
import { DataTable, type DataTableColumn } from './DataTable'
import { StatusPill } from './StatusPill'
import { CustomerProfileModal } from './CustomerProfileModal'
import { InfoTip } from '@/components/ui/info-tip'
import { getSubscriptions, type Subscription } from '@/lib/api'

function statusReason(s: Subscription): string | undefined {
  if (s.status === 'ACTIVE' || s.days_since_last == null || s.avg_interval_days == null) return undefined
  return `Son faturadan bu yana ${s.days_since_last} gün geçti (normalde ~${Math.round(s.avg_interval_days)} günde bir kesiliyor)`
}

type Status = 'loading' | 'error' | 'ready'

export function SubscriptionsTab() {
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([])
  const [status, setStatus] = useState<Status>('loading')
  const [search, setSearch] = useState('')
  const [profileClient, setProfileClient] = useState<string | null>(null)

  async function load() {
    setStatus('loading')
    const data = await getSubscriptions()
    if (data) {
      setSubscriptions(data)
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
    if (!q) return subscriptions
    return subscriptions.filter(
      (s) => s.client_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q)
    )
  }, [subscriptions, search])

  const columns: DataTableColumn<Subscription>[] = [
    {
      key: 'client',
      header: 'Müşteri',
      render: (s) => (
        <button
          onClick={() => setProfileClient(s.client_name)}
          className="hover:text-brand-dark dark:hover:text-brand text-left hover:underline"
        >
          {s.client_name}
        </button>
      ),
    },
    { key: 'product', header: 'Ürün', render: (s) => s.product_name },
    { key: 'invoice_count', header: 'Fatura Sayısı', render: (s) => String(s.invoice_count) },
    {
      key: 'days_since_last',
      header: 'Son Faturadan Bu Yana',
      render: (s) => (s.days_since_last != null ? `${s.days_since_last} gün` : '-'),
    },
    {
      key: 'status',
      header: (
        <span className="inline-flex items-center gap-1.5">
          Durum
          <InfoTip>
            <strong>Aktif</strong>: faturalama normal aralığında devam ediyor.
            <br />
            <strong>Riskli</strong>: son faturadan bu yana geçen süre, bu müşterinin normal faturalama
            aralığının 2 katını geçti — henüz kopmamış ama gecikme var, aranması önerilir.
            <br />
            <strong>Kayıp</strong>: çok daha uzun süredir hiç fatura kesilmemiş, muhtemelen abonelikten
            çıkmış. Fare ile "Riskli"/"Kayıp" etiketinin üzerine gelince o müşteriye özel gecikme
            görünür.
          </InfoTip>
        </span>
      ),
      render: (s) => <StatusPill status={s.status} title={statusReason(s)} />,
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
        emptyMessage="Henüz abonelik kaydı yok."
      />
      {profileClient && <CustomerProfileModal clientName={profileClient} onClose={() => setProfileClient(null)} />}
    </>
  )
}
