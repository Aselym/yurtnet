import { useMemo, useState } from 'react'
import { api, type QueryResult, type Sale } from '../lib/api'
import { fmt } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { BarChart, Legend, SERIES } from '../components/charts/Charts'
import { ErrorBox, Loading, Panel, Select, cn } from '../components/ui'

export default function RepsPage() {
  const { base, currency } = useWork()
  const m = currency === 'USD' ? 'net_usd' : 'net_tl'
  const t = currency === 'USD' ? 'usd' : 'tl'
  const [measure, setMeasure] = useState(m)
  const res = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', {
    ...base, direction: 'SATIS_NET', group_by: ['salesman'],
    measures: [m, currency === 'USD' ? 'profit_usd' : 'profit_tl', currency === 'USD' ? 'margin_usd' : 'margin', 'invoices', 'clients', 'items'],
  }), [JSON.stringify(base), m])
  const seri = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', {
    ...base, direction: 'SATIS_NET', group_by: ['month'], pivot_by: 'salesman', measures: [measure], pivot_limit: 8,
  }), [JSON.stringify(base), measure])
  const lic = useAsync(() => api.get<Sale[]>('/api/sales'), [])

  const lisansSay = useMemo(() => {
    const out = new Map<string, { aktif: number; yakin: number; kayip: number }>()
    lic.data?.forEach((s) => {
      const k = s.sales_rep || 'Atanmamış'
      const c = out.get(k) ?? { aktif: 0, yakin: 0, kayip: 0 }
      if (!['EXPIRED', 'NEEDS_DURATION', 'RENEWED'].includes(s.status)) { c.aktif += 1; if (s.days_left <= 90) c.yakin += 1 }
      if (s.status === 'EXPIRED') c.kayip += 1
      out.set(k, c)
    })
    return out
  }, [lic.data])

  const cols: GridCol[] = [
    ...(res.data?.columns ?? []).map((c) => ({ key: c.key, label: c.label, type: c.type, width: c.key === 'd0' ? 200 : undefined })),
    { key: '_aktif', label: 'Aktif lisans', type: 'num', render: (r) => fmt(lisansSay.get(String(r.d0))?.aktif ?? 0, 'num') },
    { key: '_yakin', label: '90 günde dolacak', type: 'num', render: (r) => fmt(lisansSay.get(String(r.d0))?.yakin ?? 0, 'num') },
    { key: '_kayip', label: 'Yenilenmemiş', type: 'num', render: (r) => fmt(lisansSay.get(String(r.d0))?.kayip ?? 0, 'num') },
  ]
  const data = useMemo(() => [...(seri.data?.rows ?? [])].sort((a, b) => String(a.d0).localeCompare(String(b.d0))), [seri.data])
  const series = (seri.data?.pivot?.values ?? []).map((v, i) => ({ key: `p::${v}`, label: String(v), color: SERIES[i % 8] }))

  return (
    <div>
      <PageHeader title="Temsilciler" subtitle="Satış temsilcisi bazında ciro, kâr, müşteri sayısı ve lisans portföyü."><FilterBar exclude={['salesman']} /></PageHeader>
      {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
      {!res.data && <Loading />}
      {res.data && (
        <div className={cn('flex flex-col gap-5', res.loading && 'opacity-60')}>
          <div className="panel p-4">
            <DataGrid id="temsilci" columns={cols} rows={res.data.rows} rowKey={(r) => String(r.d0)} totals={res.data.totals} />
          </div>
          <Panel title="Aylık dağılım" actions={<>
            <Legend series={series} />
            <Select value={measure} onChange={setMeasure} options={[
              { value: m, label: 'Tutar' }, { value: 'invoices', label: 'Fatura' }, { value: 'clients', label: 'Müşteri' },
            ]} />
          </>}>
            <BarChart data={data} xKey="d0" dim="month" type={measure === m ? t : 'num'} series={series} stacked />
          </Panel>
        </div>
      )}
    </div>
  )
}
