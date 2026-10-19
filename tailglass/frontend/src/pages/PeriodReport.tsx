import { Download, Printer } from 'lucide-react'
import { api, download } from '../lib/api'
import { fmt, fmtSpoken, rangeLabel } from '../lib/format'
import { useAsync, useLocal } from '../lib/hooks'
import { iso, today, useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { RankBars } from '../components/charts/Charts'
import { Button, ErrorBox, InfoTip, Loading, Panel, Select, cn, toast, Figure } from '../components/ui'

interface Report {
  date_from: string; date_to: string; group_by: string; group_label: string
  rows: Record<string, unknown>[]
  totals: Record<string, number | null>
  top_customers: Record<string, unknown>[]; top_suppliers: Record<string, unknown>[]
  top_items_sold: Record<string, unknown>[]; top_items_bought: Record<string, unknown>[]
}

const AYLAR = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

export default function PeriodReportPage() {
  const { base, setPeriod, from, to } = useWork()
  const [group, setGroup] = useLocal('donem.grup', 'category')
  const req = { ...base, group_by: group }
  const r = useAsync(() => api.post<Report>('/api/donem-raporu', req), [JSON.stringify(req)])
  const d = r.data

  // Son 12 ay: tek tikla ay sonu raporu
  const now = new Date()
  const aylar = Array.from({ length: 12 }, (_, i) => new Date(now.getFullYear(), now.getMonth() - i, 1))

  const cols: GridCol[] = [
    { key: 'group', label: d?.group_label ?? 'Grup', type: 'text', width: 220 },
    { key: 'open_value_tl', label: 'Dönem başı stok', type: 'tl' },
    { key: 'buy_qty', label: 'Alınan adet', type: 'num', hidden: true },
    { key: 'buy_tl', label: 'Alış', type: 'tl' },
    { key: 'buy_usd', label: 'Alış (USD)', type: 'usd', hidden: true },
    { key: 'sell_qty', label: 'Satılan adet', type: 'num', hidden: true },
    { key: 'sell_tl', label: 'Satış', type: 'tl' },
    { key: 'sell_usd', label: 'Satış (USD)', type: 'usd', hidden: true },
    { key: 'cogs_tl', label: 'Satılan malın maliyeti', type: 'tl', hidden: true },
    { key: 'profit_tl', label: 'Brüt kâr', type: 'tl' },
    { key: 'margin', label: 'Marj', type: 'pct' },
    { key: 'close_qty', label: 'Dönem sonu adet', type: 'num', hidden: true },
    { key: 'close_value_tl', label: 'Dönem sonu stok', type: 'tl' },
  ]
  const sum = (k: string) => (d?.rows ?? []).reduce((s, x) => s + (Number(x[k]) || 0), 0)
  const totals = d ? Object.fromEntries(cols.filter((c) => c.type !== 'text' && c.type !== 'pct').map((c) => [c.key, sum(c.key)])) : null
  if (totals && d) totals.margin = d.totals.margin as number

  return (
    <div>
      <PageHeader title="Dönem raporu"
        subtitle="Ay sonu (ya da seçtiğiniz herhangi bir dönem) için alışlar, satışlar ve dönem başı/sonu stok."
        actions={<>
          <Select label="Kırılım" value={group} onChange={setGroup} options={[
            { value: 'category', label: 'Kategori' }, { value: 'brand', label: 'Marka' }, { value: 'kind', label: 'Ürün türü' }, { value: 'revenue_type', label: 'Gelir tipi' },
          ]} />
          <Button icon={<Printer className="size-4" />} onClick={() => window.print()}>PDF / yazdır</Button>
          <Button variant="primary" icon={<Download className="size-4" />}
            onClick={() => download('/api/export/donem', { request: req, filename: `Dönem raporu ${rangeLabel(from, to)}` }).catch((e) => toast.err(e.message))}>
            Excel'e aktar
          </Button>
        </>}>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {aylar.map((a) => {
            const f = iso(a), t0 = iso(new Date(a.getFullYear(), a.getMonth() + 1, 0))
            const t = t0 > today() ? today() : t0
            const on = from === f && to === t
            return (
              <button key={f} onClick={() => setPeriod(f, t)}
                className={cn('h-7 rounded-full px-3 text-[12.5px]', on ? 'bg-ink font-medium text-surface' : 'border border-line bg-surface text-ink-2 hover:text-ink')}>
                {AYLAR[a.getMonth()]} {a.getFullYear() !== now.getFullYear() ? a.getFullYear() : ''}
              </button>
            )
          })}
        </div>
        <FilterBar />
      </PageHeader>

      {r.error && <ErrorBox message={r.error} onRetry={r.reload} />}
      {!d && r.loading && <Loading />}
      {d && (
        <div className={cn('flex flex-col gap-5', r.loading && 'opacity-60')}>
          <h2 className="display text-[22px] font-semibold">{rangeLabel(d.date_from, d.date_to)}</h2>
          <StockFlow t={d.totals} />

          <div className="panel p-4">
            <DataGrid id="donem" columns={cols} rows={d.rows} rowKey={(x) => String(x.group)} totals={totals} />
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 2xl:grid-cols-4">
            {([
              ['En çok satış yapılan müşteriler', d.top_customers, 'var(--s1)'], ['En çok alış yapılan tedarikçiler', d.top_suppliers, 'var(--s2)'],
              ['En çok satılan ürünler', d.top_items_sold, 'var(--s1)'], ['En çok alınan ürünler', d.top_items_bought, 'var(--s2)'],
            ] as const).map(([t, rows, c]) => (
              <Panel key={t} title={t}><RankBars rows={rows} labelKey="d0" valueKey="m_net_tl" type="tl" color={c} /></Panel>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StockFlow({ t }: { t: Record<string, number | null> }) {
  const adimlar: { l: string; v: number | null | undefined; op?: string; hint?: string; strong?: boolean }[] = [
    { l: 'Dönem başı stok', v: t.open_value_tl, hint: 'Dönemin ilk gününden bir önceki gün eldeki stok, son alış fiyatıyla değerlenmiş.' },
    { l: 'Alışlar', v: t.buy_tl, op: '+' },
    { l: 'Satılan malın maliyeti', v: t.cogs_tl, op: '−', hint: 'Satılan ürünlerin FIFO yöntemine göre tahmini alış maliyeti.' },
    { l: 'Dönem sonu stok', v: t.close_value_tl, op: '=', strong: true, hint: 'Dönemin son günü eldeki stok. Değerleme son alış fiyatıyla yapıldığı için akıştaki toplamla küçük fark olabilir (fiyat değişimleri, sayım/fire hareketleri).' },
  ]
  return (
    <section className="panel overflow-hidden">
      <div className="grid grid-cols-1 gap-px bg-line sm:grid-cols-2 xl:grid-cols-4">
        {adimlar.map((a) => (
          <div key={a.l} className={cn('relative px-5 py-4', a.strong ? 'bg-surface-2' : 'bg-surface')}>
            {a.op && <span className="display absolute top-3 right-4 text-[22px] text-muted" aria-hidden>{a.op}</span>}
            <p className="flex items-center gap-1.5 text-[12.5px] text-ink-2">{a.l}{a.hint && <InfoTip>{a.hint}</InfoTip>}</p>
            <div className="mt-1 text-[21px] font-semibold"><Figure value={a.v} type="tl" /></div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-4 border-t border-line px-5 py-4 md:grid-cols-3 2xl:grid-cols-6">
        {[
          ['Satış', fmt(t.sell_tl, 'tl'), fmtSpoken(t.sell_tl, 'tl')],
          ['Brüt kâr', fmt(t.profit_tl, 'tl'), t.margin != null ? `marj ${fmt(t.margin, 'pct')}` : ''],
          ['Satış (USD)', fmt(t.sell_usd, 'usd'), fmtSpoken(t.sell_usd, 'usd')],
          ['Satış faturası', fmt(t.sell_invoices, 'num'), `${fmt(t.clients, 'num')} müşteri`],
          ['Alış faturası', fmt(t.buy_invoices, 'num'), fmt(t.buy_usd, 'usd')],
          ['Dönem sonu stok (USD)', fmt(t.close_value_usd, 'usd'), `${fmt(t.close_qty, 'num')} adet`],
        ].map(([l, v, s]) => (
          <div key={l}>
            <p className="text-[12.5px] text-ink-2">{l}</p>
            <p className="tnum text-[16px] font-semibold">{v}</p>
            <p className="tnum text-[12px] text-muted">{s}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
