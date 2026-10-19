import { useMemo, useState } from 'react'
import { Download, Pin, Plus, Search, X } from 'lucide-react'
import { api, download, type QueryResult } from '../lib/api'
import { fmt, fmtDate } from '../lib/format'
import { useAsync, useDebounced, useLocal } from '../lib/hooks'
import { filterValues, useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { BarChart, Legend, RankBars } from '../components/charts/Charts'
import { Badge, Button, Drawer, ErrorBox, InfoTip, Loading, Panel, Popover, Segmented, Select, cn, inputCls, toast, Figure } from '../components/ui'

interface StockRow {
  item_ref: number; item: string; item_code: string; brand: string; category: string; qty: number
  unit_cost_tl: number | null; value_tl: number | null; value_usd: number | null; last_purchase: string | null
  last_sale: string | null; last_move: string | null; days_since_move: number | null; sold_recent: number
  cover_days: number | null; [k: string]: unknown
}
interface StockResult {
  as_of: string; velocity_days: number; rows: StockRow[]
  totals: { items: number; qty: number; value_tl: number; value_usd: number; dead_items: number; dead_value_tl: number }
}

export default function StockPage() {
  const { to, filters, setFilter, meta, reloadMeta } = useWork()
  const [tab, setTab] = useLocal<'stok' | 'performans'>('stok.tab', 'stok')
  const pinned = (meta?.settings?.pinned_brands ?? 'Dell').split(',').map((s) => s.trim()).filter(Boolean)
  const activeBrand = filterValues(filters.brand)
  const brandTab = activeBrand.length === 1 && pinned.includes(activeBrand[0]) ? activeBrand[0] : activeBrand.length ? null : 'Tümü'

  const savePinned = async (list: string[]) => {
    try {
      await api.post('/api/settings', { pinned_brands: list.join(',') })
      await reloadMeta()
    } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') }
  }

  return (
    <div>
      <PageHeader title="Ürünler ve stok"
        subtitle="Eldeki stok, değeri, ne zamandır beklediği ve ürün bazında satış performansı."
        actions={<Segmented value={tab} onChange={setTab} options={[
          { value: 'stok', label: 'Stok durumu' }, { value: 'performans', label: 'Ürün performansı' },
        ]} />}>
        <div className="mb-3 flex flex-wrap items-center gap-1.5" role="tablist" aria-label="Sabit marka sekmeleri">
          {['Tümü', ...pinned].map((b) => (
            <span key={b} className="group relative">
              <button role="tab" aria-selected={brandTab === b}
                onClick={() => setFilter('brand', b === 'Tümü' ? null : [b])}
                className={cn('h-8 rounded-[var(--radius-ctl)] px-3.5 text-[13px] font-medium transition-colors',
                  brandTab === b ? 'bg-ink text-surface' : 'bg-surface text-ink-2 ring-1 ring-line hover:text-ink')}>
                {b}
              </button>
              {b !== 'Tümü' && (
                <button onClick={() => savePinned(pinned.filter((x) => x !== b))} aria-label={`${b} sekmesini kaldır`}
                  className="absolute -top-1.5 -right-1.5 hidden size-4 items-center justify-center rounded-[var(--radius-ctl)] bg-ink-2 text-surface group-hover:flex">
                  <X className="size-3" />
                </button>
              )}
            </span>
          ))}
          <PinBrand pinned={pinned} onAdd={(b) => savePinned([...pinned, b])} />
        </div>
        <FilterBar />
      </PageHeader>
      {tab === 'stok' ? <StockView defaultAsOf={to} /> : <PerformanceView />}
    </div>
  )
}

function PinBrand({ pinned, onAdd }: { pinned: string[]; onAdd: (b: string) => void }) {
  const { base } = useWork()
  const [q, setQ] = useState('')
  const opts = useAsync(() => api.post<Record<string, { v: string; n: number }[]>>('/api/analiz/secenekler', { ...base, filters: {} }), [base.date_from, base.date_to])
  const list = (opts.data?.brand ?? []).filter((x) => !pinned.includes(x.v) && x.v.toLowerCase().includes(q.toLowerCase()))
  return (
    <Popover width={240} trigger={(_, toggle) => (
      <button onClick={toggle} title="Markayı sabit sekme yap"
        className="inline-flex h-8 items-center gap-1 rounded-[var(--radius-ctl)] border border-dashed border-line-strong px-3 text-[13px] text-ink-2 hover:text-ink">
        <Pin className="size-3.5" /> Sekme ekle
      </button>
    )}>
      {(close) => (
        <div>
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Marka ara" className="h-10 w-full border-b border-line bg-transparent px-3 text-sm outline-none" />
          <ul className="scroll-thin max-h-64 overflow-auto py-1">
            {list.map((b) => (
              <li key={b.v}><button onClick={() => { onAdd(b.v); close() }} className="flex w-full items-center justify-between px-3 py-1.5 text-[13px] hover:bg-surface-2">
                <span>{b.v}</span><Plus className="size-3.5 text-muted" /></button></li>
            ))}
          </ul>
        </div>
      )}
    </Popover>
  )
}

// ------------------------------------------------------------------ stok
function StockView({ defaultAsOf }: { defaultAsOf: string }) {
  const { filters, currency, setFilter } = useWork()
  const [asOf, setAsOf] = useState<string | null>(null)
  const tarih = asOf ?? defaultAsOf
  const [velocity, setVelocity] = useLocal('stok.hiz', '90')
  const [onlyIn, setOnlyIn] = useLocal('stok.eldeki', true)
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 300)
  const [open, setOpen] = useState<StockRow | null>(null)
  const stokFiltre = useMemo(() => Object.fromEntries(['brand', 'category', 'kind', 'item']
    .filter((k) => filters[k]).map((k) => [k, filterValues(filters[k])])), [filters])

  const res = useAsync(() => api.post<StockResult>('/api/stok', {
    as_of: tarih, velocity_days: Number(velocity), only_in_stock: onlyIn, filters: stokFiltre, search: dq,
  }), [tarih, velocity, onlyIn, JSON.stringify(stokFiltre), dq])

  const byCat = useMemo(() => {
    const m = new Map<string, number>()
    res.data?.rows.forEach((r) => m.set(r.category, (m.get(r.category) || 0) + (r.value_tl || 0)))
    return [...m.entries()].map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v).slice(0, 10)
  }, [res.data])

  const cols: GridCol<StockRow>[] = [
    { key: 'item', label: 'Ürün', type: 'text', width: 340 },
    { key: 'item_code', label: 'Kod', type: 'text', hidden: true },
    { key: 'brand', label: 'Marka', type: 'text', width: 130 },
    { key: 'category', label: 'Kategori', type: 'text', width: 160 },
    { key: 'qty', label: 'Eldeki adet', type: 'num', width: 110 },
    { key: 'unit_cost_tl', label: 'Son alış birim', type: 'tl', hidden: true },
    { key: 'value_tl', label: 'Değer (TL)', type: 'tl', hidden: currency === 'USD' },
    { key: 'value_usd', label: 'Değer (USD)', type: 'usd', hidden: currency === 'TL' },
    { key: 'last_purchase', label: 'Son alış', type: 'date', width: 110 },
    { key: 'last_sale', label: 'Son satış', type: 'date', width: 110 },
    {
      key: 'days_since_move', label: 'Hareketsiz', type: 'num', width: 120,
      render: (r) => r.days_since_move == null ? '—' : (
        <span className="inline-flex items-center justify-end gap-1.5">
          {r.days_since_move > 180 && <Badge tone="critical">ölü</Badge>}
          <span className="tnum">{r.days_since_move} gün</span>
        </span>
      ),
    },
    { key: 'sold_recent', label: `Son ${velocity} gün satış`, type: 'num', width: 140 },
    { key: 'cover_days', label: 'Kaç gün yeter', type: 'num', width: 120 },
  ]

  const t = res.data?.totals
  return (
    <div className="flex flex-col gap-5">
      <div className="panel grid grid-cols-2 divide-line max-md:divide-y md:grid-cols-4 md:divide-x">
        {[
          ['Stok değeri', <Figure value={currency === 'USD' ? t?.value_usd : t?.value_tl} type={currency === 'USD' ? 'usd' : 'tl'} />, 'Eldeki adet × o tarihe kadarki son alış birim fiyatı (yaklaşık).'],
          ['Ürün çeşidi', fmt(t?.items, 'num'), null],
          ['Toplam adet', fmt(t?.qty, 'num'), null],
          ['Ölü stok', <Figure value={t?.dead_value_tl} type="tl" />, `180 günden uzun süredir hiç hareket görmemiş ${t?.dead_items ?? 0} ürün.`],
        ].map(([l, v, h]) => (
          <div key={l as string} className="px-5 py-4">
            <p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">{l}{h && <InfoTip>{h}</InfoTip>}</p>
            <div className={cn('tnum mt-0.5 text-[21px] font-semibold', l === 'Ölü stok' && 'text-neg')}>{v}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="panel p-4">
          {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
          {!res.data && res.loading && <Loading />}
          {res.data && (
            <DataGrid id="stok" columns={cols} rows={res.data.rows} rowKey={(r) => r.item_ref} onRowClick={setOpen}
              sort={undefined}
              toolbarLeft={<>
                <label className="flex items-center gap-2 text-[13px] text-ink-2">
                  Tarih
                  <input type="date" value={tarih} onChange={(e) => setAsOf(e.target.value)} className={cn(inputCls, 'h-8 w-40')} />
                </label>
                <Select label="Satış hızı" value={velocity} onChange={setVelocity} options={[
                  { value: '30', label: 'Son 30 gün' }, { value: '90', label: 'Son 90 gün' }, { value: '180', label: 'Son 180 gün' }, { value: '365', label: 'Son 365 gün' },
                ]} />
                <label className="flex items-center gap-2 text-[13px] text-ink-2">
                  <input type="checkbox" checked={onlyIn} onChange={(e) => setOnlyIn(e.target.checked)} className="accent-[var(--brand)]" />
                  Sadece eldekiler
                </label>
                <label className="relative">
                  <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" />
                  <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ürün ya da kod" className={cn(inputCls, 'h-8 w-52 pl-8 text-[13px]')} />
                </label>
              </>}
              toolbarRight={<Button size="sm" icon={<Download className="size-4" />} onClick={() =>
                download('/api/export/stok', { request: { as_of: tarih, velocity_days: Number(velocity), only_in_stock: onlyIn, filters: stokFiltre, search: dq }, filename: `Stok ${tarih}` })
                  .catch((e) => toast.err(e.message))}>Excel</Button>}
            />
          )}
        </div>
        <Panel title="Kategoriye göre stok değeri" hint="Kategoriye tıklarsanız filtre olarak eklenir.">
          <RankBars rows={byCat.map((x) => ({ k: x.k, v: x.v }))} labelKey="k" valueKey="v" type="tl" color="var(--s1)"
            onClick={(r) => setFilter('category', [String(r.k)])} />
        </Panel>
      </div>
      <ItemDrawer row={open} onClose={() => setOpen(null)} />
    </div>
  )
}

export function ItemDrawer({ row, onClose }: { row: { item: string; item_code?: string; brand?: string; category?: string } | null; onClose: () => void }) {
  const { base } = useWork()
  const item = row?.item
  const hist = useAsync(() => item
    ? api.post<QueryResult>('/api/analiz/sorgu', {
      date_from: '1900-01-01', date_to: base.date_to, filters: { item: [item] }, direction: 'TUMU', group_by: ['month'],
      pivot_by: 'direction', measures: ['qty'],
    })
    : Promise.resolve(null), [item, base.date_to])
  const lines = useAsync(() => item
    ? api.post<{ rows: Record<string, unknown>[]; total: number }>('/api/analiz/satirlar', {
      date_from: '1900-01-01', date_to: base.date_to, filters: { item: [item] }, direction: 'TUMU', limit: 200,
    })
    : Promise.resolve(null), [item, base.date_to])
  const data = useMemo(() => [...(hist.data?.rows ?? [])].sort((a, b) => String(a.d0).localeCompare(String(b.d0))).slice(-36), [hist.data])
  return (
    <Drawer open={!!row} onClose={onClose} title={row?.item ?? ''} subtitle={[row?.brand, row?.category, row?.item_code].filter(Boolean).join(', ')}>
      {hist.loading && <Loading />}
      {data.length > 0 && (
        <section className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold">Aylık hareket (adet, son 36 ay)</h3>
            <Legend series={[{ key: 'a', label: 'Alış', color: 'var(--s2)' }, { key: 's', label: 'Satış', color: 'var(--rev-product)' }]} />
          </div>
          <BarChart data={data} xKey="d0" dim="month" type="num" stacked={false} height={200}
            series={[{ key: 'p::Alış', label: 'Alış', color: 'var(--s2)' }, { key: 'p::Satış', label: 'Satış', color: 'var(--rev-product)' }]} />
        </section>
      )}
      <h3 className="mb-2 text-[14px] font-semibold">Tüm hareketler {lines.data && <span className="font-normal text-muted">({lines.data.total.toLocaleString('tr-TR')})</span>}</h3>
      <table className="w-full text-[12.5px]">
        <thead className="text-left text-ink-2">
          <tr className="border-b border-line"><th className="py-1.5 font-medium">Tarih</th><th className="font-medium">Hareket</th><th className="font-medium">Cari</th>
            <th className="text-right font-medium">Adet</th><th className="text-right font-medium">Tutar</th><th className="text-right font-medium">Alış tarihi</th></tr>
        </thead>
        <tbody>
          {(lines.data?.rows ?? []).map((r, i) => (
            <tr key={i} className="border-b border-line/70">
              <td className="tnum py-1.5">{fmtDate(r.date as string)}</td>
              <td>{String(r.direction)}</td>
              <td className="max-w-[220px] truncate">{String(r.client)}</td>
              <td className="tnum text-right">{fmt(r.qty, 'num')}</td>
              <td className="tnum text-right">{fmt(r.net_tl, 'tl')}</td>
              <td className="tnum text-right">{fmtDate(r.cost_date as string)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Drawer>
  )
}

// ------------------------------------------------------------------ performans
function PerformanceView() {
  const { base, currency } = useWork()
  const money = currency === 'USD' ? ['net_usd', 'profit_usd', 'margin_usd'] : currency === 'TL' ? ['net_tl', 'profit_tl', 'margin'] : ['net_tl', 'net_usd', 'profit_tl', 'margin']
  const measures = ['qty', ...money, 'clients', 'avg_price_tl', 'stock_age']
  const res = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', {
    ...base, direction: 'SATIS_NET', group_by: ['item', 'brand', 'category'], measures, sort: { key: `m_${money[0]}`, desc: true },
  }), [JSON.stringify(base), measures.join()])
  const [open, setOpen] = useState<Record<string, unknown> | null>(null)
  if (res.error) return <ErrorBox message={res.error} onRetry={res.reload} />
  if (!res.data) return <Loading />
  const cols: GridCol[] = res.data.columns.map((c) => ({
    key: c.key, label: c.label, type: c.type, width: c.key === 'd0' ? 340 : undefined,
    render: c.measure === 'stock_age' ? (r: Record<string, unknown>) => r[c.key] == null ? '—' : `${Math.round(r[c.key] as number)} gün` : undefined,
  }))
  return (
    <div className={cn('panel p-4', res.loading && 'opacity-60')}>
      <DataGrid id="performans" columns={cols} rows={res.data.rows} rowKey={(r) => `${r.d0}|${r.d1}`} totals={res.data.totals}
        onRowClick={(r) => setOpen(r)}
        toolbarLeft={<span className="text-[13px] text-ink-2">{res.data.row_count.toLocaleString('tr-TR')} ürün satıldı</span>}
        toolbarRight={<Button size="sm" icon={<Download className="size-4" />} onClick={() =>
          download('/api/export/sorgu', { request: { ...base, direction: 'SATIS_NET', group_by: ['item', 'brand', 'category'], measures }, title: 'Ürün performansı', filename: 'Ürün performansı' })
            .catch((e) => toast.err(e.message))}>Excel</Button>} />
      <ItemDrawer row={open ? { item: String(open.d0), brand: String(open.d1), category: String(open.d2) } : null} onClose={() => setOpen(null)} />
    </div>
  )
}
