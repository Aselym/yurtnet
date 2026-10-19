import { useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { api, type Subscription } from '../lib/api'
import { fmt } from '../lib/format'
import { useAsync, useLocal } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { CustomerDrawer } from './Customers'
import { Badge, ErrorBox, InfoTip, Loading, Segmented, cn, inputCls } from '../components/ui'

type Tab = 'tumu' | 'ACTIVE' | 'AT_RISK' | 'LOST'

export default function SubscriptionsPage() {
  const { meta } = useWork()
  const res = useAsync(() => api.get<Subscription[]>('/api/subscriptions'), [])
  const gruplar = useAsync(() => api.get<{ client_name: string; group_name: string }[]>('/api/firma-gruplari'), [])
  const [tab, setTab] = useLocal<Tab>('abonelik.tab', 'tumu')
  const [q, setQ] = useState('')
  const [open, setOpen] = useState<{ name: string; group: boolean } | null>(null)
  const grupAdlari = useMemo(() => new Set((gruplar.data ?? []).map((g) => g.group_name)), [gruplar.data])
  const s = meta?.settings
  const kat = Number(s?.sub_risk_factor ?? 2)

  const list = res.data ?? []
  const rows = list
    .filter((x) => tab === 'tumu' || x.status === tab)
    .filter((x) => !q || `${x.client_name} ${x.product_name}`.toLocaleLowerCase('tr').includes(q.toLocaleLowerCase('tr')))
  const say = (st: string) => list.filter((x) => x.status === st).length

  const cols: GridCol<Subscription & Record<string, unknown>>[] = [
    { key: 'client_name', label: 'Müşteri / firma grubu', type: 'text', width: 320, render: (x) => (
      <span className="inline-flex items-center gap-2">{x.client_name}{grupAdlari.has(x.client_name) && <Badge tone="brand">grup</Badge>}</span>
    ) },
    { key: 'product_name', label: 'Ürün', type: 'text', width: 340 },
    { key: 'invoice_count', label: 'Fatura', type: 'num', width: 90 },
    { key: 'avg_interval_days', label: 'Normal aralık', type: 'num', width: 120, render: (x) => x.avg_interval_days ? `~${Math.round(x.avg_interval_days)} gün` : '—' },
    { key: 'last_invoice_date', label: 'Son fatura', type: 'date', width: 110 },
    { key: 'days_since_last', label: 'Geçen süre', type: 'num', width: 110, render: (x) => `${x.days_since_last} gün` },
    { key: 'status', label: 'Durum', type: 'text', width: 140, render: (x) => {
      const neden = `Son faturadan bu yana ${x.days_since_last} gün geçti; normalde ~${Math.round(x.avg_interval_days ?? 30)} günde bir kesiliyor.`
      return (
        <span title={x.status !== 'ACTIVE' ? neden : undefined}>
          {x.status === 'ACTIVE' ? <Badge tone="good">Aktif</Badge> : x.status === 'AT_RISK' ? <Badge tone="warning">Riskli</Badge> : <Badge tone="critical">Kayıp</Badge>}
        </span>
      )
    } },
    { key: 'first_invoice_date', label: 'İlk fatura', type: 'date', hidden: true },
  ]

  return (
    <div>
      <PageHeader title="Abonelikler"
        subtitle={<>Aylık faturalanan abonelikler (Microsoft, Azure vb.). Süresi dolmaz; her müşterinin kendi normal faturalama aralığına göre gecikme izlenir.</>} />
      {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
      {!res.data && res.loading && <Loading />}
      {res.data && (
        <div className="flex flex-col gap-5">
          <div className="panel grid grid-cols-1 divide-line max-md:divide-y md:grid-cols-3 md:divide-x">
            {[
              ['Aktif', say('ACTIVE'), 'Son faturadan bu yana geçen süre normal aralığın içinde.'],
              ['Riskli', say('AT_RISK'), `Geçen süre, müşterinin normal faturalama aralığının ${kat} katını aştı. Fatura yan firmaya kesiliyorsa müşteri profilinden firma grubuna bağlayın; risk kalkar.`],
              ['Kayıp', say('LOST'), `Geçen süre normal aralığın ${kat * 2} katını aştı: müşteri muhtemelen abonelikten çıktı.`],
            ].map(([l, v, h]) => (
              <div key={l as string} className="px-5 py-4">
                <p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">{l}<InfoTip>{h}</InfoTip></p>
                <p className="tnum mt-0.5 text-[21px] font-semibold">{fmt(v, 'num')}</p>
              </div>
            ))}
          </div>
          <div className="panel p-4">
            <DataGrid id="abonelik" columns={cols} rows={rows as (Subscription & Record<string, unknown>)[]} rowKey={(x) => x.id}
              onRowClick={(x) => setOpen({ name: x.client_name, group: grupAdlari.has(x.client_name) })}
              toolbarLeft={<>
                <Segmented size="sm" value={tab} onChange={setTab} options={[
                  { value: 'tumu', label: `Tümü (${list.length})` }, { value: 'AT_RISK', label: `Riskli (${say('AT_RISK')})` },
                  { value: 'ACTIVE', label: `Aktif (${say('ACTIVE')})` }, { value: 'LOST', label: `Kayıp (${say('LOST')})` },
                ]} />
                <label className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Müşteri ya da ürün" className={cn(inputCls, 'h-8 w-56 pl-8 text-[13px]')} />
                </label>
              </>}
              toolbarRight={<a href="#/ayarlar" className="text-[12.5px] text-ink-2 underline-offset-2 hover:underline">Risk eşiklerini değiştir</a>} />
          </div>
        </div>
      )}
      <CustomerDrawer name={open?.name ?? null} dim={open?.group ? 'client_group' : 'client'} onClose={() => { setOpen(null); gruplar.reload(); res.reload() }} />
    </div>
  )
}
