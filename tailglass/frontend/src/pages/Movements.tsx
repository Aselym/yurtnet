import { useEffect, useMemo, useState } from 'react'
import { Download, Search } from 'lucide-react'
import { api, download, type Column, type Direction, type LinesResult, type QueryResult } from '../lib/api'
import { fmt, fmtPeriodKey } from '../lib/format'
import { useAsync, useDebounced, useLocal } from '../lib/hooks'
import { moneyMeasures, useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { Badge, Button, ErrorBox, InfoTip, Loading, Segmented, Select, cn, inputCls, toast, Figure } from '../components/ui'

const GRUPLAR = [
  { value: 'client', label: 'Müşteri / cari' }, { value: 'client_group', label: 'Firma grubu' },
  { value: 'item', label: 'Ürün' }, { value: 'brand', label: 'Marka' }, { value: 'category', label: 'Kategori' },
  { value: 'salesman', label: 'Temsilci' }, { value: 'city', label: 'Şehir' }, { value: 'month', label: 'Ay' },
  { value: 'kind', label: 'Ürün türü' }, { value: 'aging_bucket', label: 'Depoda bekleme süresi' },
]

export default function Movements({ direction }: { direction: Direction }) {
  const satis = direction.startsWith('SATIS')
  const { base, currency, meta } = useWork()
  const [netMi, setNetMi] = useLocal(`hareket.${satis ? 's' : 'a'}.net`, true)
  const dir = (satis ? (netMi ? 'SATIS_NET' : 'SATIS') : (netMi ? 'ALIS_NET' : 'ALIS')) as Direction
  const [mode, setMode] = useLocal<'lines' | 'grouped'>(`hareket.${satis ? 's' : 'a'}.mod`, 'grouped')
  const [group, setGroup] = useLocal(`hareket.${satis ? 's' : 'a'}.grup`, 'client')
  const [q, setQ] = useState('')
  const dq = useDebounced(q, 350)

  const money = moneyMeasures(currency)
  const ozetOlcu = [...new Set(['net_tl', 'net_usd', 'qty', 'lines', 'invoices', 'clients', ...(satis ? ['profit_tl', 'margin', 'stock_age'] : [])])]
  const ozet = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', { ...base, direction: dir, search: dq, measures: ozetOlcu }),
    [JSON.stringify(base), dir, dq])
  const t = ozet.data?.totals

  const exportReq = (body: object, kind: 'sorgu' | 'satirlar') => download(`/api/export/${kind}`, {
    request: body, title: satis ? 'Satışlar' : 'Alışlar', filename: satis ? 'Satışlar' : 'Alışlar',
  }).catch((e) => toast.err(e.message))

  const grupOlcu = [...money, 'qty', 'invoices', ...(group !== 'client' && group !== 'client_group' ? ['clients'] : ['items']),
    ...(satis ? ['profit_tl', 'margin', 'stock_age'] : [])]

  return (
    <div>
      <PageHeader
        title={satis ? 'Satışlar' : 'Alışlar'}
        subtitle={satis
          ? 'Logo\'daki satış faturası satırları. Alış tarihi ve kâr, satılan ürünün hangi alıştan karşılandığına göre (FIFO) tahmin edilir.'
          : 'Logo\'daki alış faturası satırları: tedarikçiden ne, ne zaman, kaça alındı.'}
        actions={<>
          <Segmented value={netMi ? 'net' : 'brut'} onChange={(v) => setNetMi(v === 'net')} options={[
            { value: 'net', label: 'İadeler düşülmüş' }, { value: 'brut', label: 'Brüt' },
          ]} />
          <Button icon={<Download className="size-4" />} onClick={() => mode === 'lines'
            ? exportReq({ ...base, direction: dir, search: dq }, 'satirlar')
            : exportReq({ ...base, direction: dir, search: dq, group_by: [group], measures: grupOlcu }, 'sorgu')}>
            Excel'e aktar
          </Button>
        </>}
      >
        <FilterBar />
      </PageHeader>

      <div className="panel mb-5 flex flex-wrap divide-line max-md:divide-y md:divide-x">
        {[
          ['Tutar', <Figure value={currency === 'USD' ? t?.m_net_usd : t?.m_net_tl} type={currency === 'USD' ? 'usd' : 'tl'} />, currency === 'BOTH' ? fmt(t?.m_net_usd, 'usd') : null],
          ['Adet', fmt(t?.m_qty, 'num'), null],
          ['Fatura', fmt(t?.m_invoices, 'num'), `${fmt(t?.m_lines, 'num')} satır`],
          [satis ? 'Müşteri' : 'Tedarikçi', fmt(t?.m_clients, 'num'), null],
          ...(satis ? [
            ['Brüt kâr (FIFO)', <Figure value={t?.m_profit_tl} type="tl" />, t?.m_margin != null ? `marj ${fmt(t?.m_margin, 'pct')}` : null],
            ['Ort. depoda bekleme', t?.m_stock_age != null ? `${Math.round(t.m_stock_age as number)} gün` : '—', null],
          ] : []),
        ].map(([l, v, s]) => (
          <div key={l as string} className={cn('flex-1 px-5 py-3.5', typeof v === 'string' ? 'min-w-[150px]' : 'min-w-[240px]')}>
            <p className="text-[12.5px] text-ink-2">{l}</p>
            <div className={cn('tnum mt-0.5 text-[19px] font-semibold', ozet.loading && 'opacity-50')}>{v}</div>
            {s && <p className="tnum text-[12px] text-muted">{s}</p>}
          </div>
        ))}
      </div>

      <div className="panel p-4">
        {mode === 'lines'
          ? <LinesView dir={dir} search={dq} satis={satis}
              toolbar={<Toolbar satis={satis} mode={mode} setMode={setMode} group={group} setGroup={setGroup} q={q} setQ={setQ} />} />
          : <GroupedView dir={dir} search={dq} satis={satis} group={group} measures={grupOlcu}
              toolbar={<Toolbar satis={satis} mode={mode} setMode={setMode} group={group} setGroup={setGroup} q={q} setQ={setQ} />} />}
      </div>
      {!meta?.data.lines && <p className="mt-4 text-[13px] text-ink-2">Henüz veri yok. Üstteki senkron düğmesiyle Logo'dan veri çekin.</p>}
    </div>
  )
}

function Toolbar({ satis, mode, setMode, group, setGroup, q, setQ }: {
  satis: boolean
  mode: 'lines' | 'grouped'; setMode: (m: 'lines' | 'grouped') => void; group: string; setGroup: (g: string) => void
  q: string; setQ: (s: string) => void
}) {
  return (
    <>
      <Segmented value={mode} onChange={setMode} options={[
        { value: 'grouped', label: 'Gruplu' }, { value: 'lines', label: 'Satır satır' },
      ]} />
      {mode === 'grouped' && <Select label="Grupla:" value={group} onChange={setGroup} options={satis ? GRUPLAR : GRUPLAR.filter((g) => g.value !== 'aging_bucket').map((g) => g.value === 'client' ? { ...g, label: 'Tedarikçi' } : g)} />}
      <label className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={satis ? 'Ürün, müşteri, fiş no ara' : 'Ürün, tedarikçi, fiş no ara'}
          className={cn(inputCls, 'h-8 w-60 pl-8 text-[13px]')} />
      </label>
    </>
  )
}

// ------------------------------------------------------------------ satir gorunumu
export function lineColumns(cols: Column[], satis: boolean, currency: string): GridCol[] {
  const gizli = new Set(['client_group', 'city', 'item_code', 'kind', 'rate', 'cost_tl', 'cost_usd', 'profit_usd', 'direction'])
  if (!satis) ['cost_date', 'stock_age', 'profit_tl'].forEach((k) => gizli.add(k))
  if (currency === 'USD') { gizli.add('net_tl'); gizli.add('price_tl'); gizli.add('profit_tl'); gizli.delete('profit_usd') }
  if (currency === 'TL') gizli.add('net_usd')
  return cols
    .filter((c) => satis || !['cost_date', 'stock_age', 'profit_tl', 'profit_usd', 'cost_tl', 'cost_usd'].includes(c.key))
    .map((c) => ({
      key: c.key, label: c.key === 'client' && !satis ? 'Tedarikçi' : c.label, type: c.type, hidden: gizli.has(c.key),
      width: c.key === 'date' || c.key === 'cost_date' ? 110 : c.key === 'qty' ? 80 : undefined,
      render: c.key === 'direction'
        ? (r: Record<string, unknown>) => <Badge tone={String(r.direction).includes('iade') ? 'serious' : 'neutral'}>{String(r.direction)}</Badge>
        : c.key === 'stock_age'
          ? (r: Record<string, unknown>) => r.stock_age == null ? '—' : <span className={cn('tnum', (r.stock_age as number) > 180 && 'font-medium text-neg')}>{fmt(r.stock_age, 'num')} gün</span>
          : undefined,
    }))
}

function LinesView({ dir, search, satis, toolbar, extraFilters, compact }: {
  dir: Direction; search: string; satis: boolean; toolbar?: React.ReactNode; extraFilters?: Record<string, string[]>; compact?: boolean
}) {
  const { base, currency } = useWork()
  const [sort, setSort] = useState({ key: 'date', desc: true })
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [cols, setCols] = useState<Column[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const sayfa = compact ? 50 : 300
  const filters = useMemo(() => ({ ...base.filters, ...(extraFilters || {}) }), [base.filters, extraFilters])
  const key = JSON.stringify([base.date_from, base.date_to, filters, dir, search, sort])

  const yukle = async (offset: number) => {
    setLoading(true)
    setErr(null)
    try {
      const r = await api.post<LinesResult>('/api/analiz/satirlar', {
        date_from: base.date_from, date_to: base.date_to, filters, direction: dir, search, sort, limit: sayfa, offset,
      })
      setCols(r.columns)
      setTotal(r.total)
      setRows((p) => (offset ? [...p, ...r.rows] : r.rows))
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Yüklenemedi.')
    } finally {
      setLoading(false)
    }
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { yukle(0) }, [key])

  if (err) return <ErrorBox message={err} onRetry={() => yukle(0)} />
  return (
    <div>
      <DataGrid id={`satirlar.${satis ? 's' : 'a'}${compact ? '.k' : ''}`} columns={lineColumns(cols, satis, currency)} rows={rows}
        rowKey={(_, i) => i} sort={sort} onSort={(s) => setSort(s)} dense={compact} maxHeight={compact ? 360 : 640}
        toolbarLeft={toolbar} toolbarRight={<span className="tnum text-[12.5px] text-muted">{rows.length.toLocaleString('tr-TR')} / {total.toLocaleString('tr-TR')} satır</span>}
        emptyText={loading ? 'Yükleniyor…' : 'Bu seçimde hareket yok.'} />
      {rows.length < total && (
        <div className="mt-3 flex justify-center">
          <Button size="sm" loading={loading} onClick={() => yukle(rows.length)}>
            {Math.min(sayfa, total - rows.length).toLocaleString('tr-TR')} satır daha yükle
          </Button>
        </div>
      )}
    </div>
  )
}

// ------------------------------------------------------------------ gruplu gorunum
function GroupedView({ dir, search, satis, group, measures, toolbar }: {
  dir: Direction; search: string; satis: boolean; group: string; measures: string[]; toolbar: React.ReactNode
}) {
  const { base } = useWork()
  const res = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', {
    ...base, direction: dir, search, group_by: [group], measures, sort: { key: group === 'month' ? 'd0' : `m_${measures[0]}`, desc: true },
  }), [JSON.stringify(base), dir, search, group, measures.join()])

  const cols: GridCol[] = useMemo(() => (res.data?.columns ?? []).map((c) => ({
    key: c.key, label: c.key === 'd0' && group === 'client' && !satis ? 'Tedarikçi' : c.label, type: c.type, dim: c.dim,
    render: c.measure === 'stock_age' ? (r: Record<string, unknown>) => r[c.key] == null ? '—' : `${Math.round(r[c.key] as number)} gün` : undefined,
  })), [res.data, group, satis])

  if (res.error) return <ErrorBox message={res.error} onRetry={res.reload} />
  if (!res.data) return <Loading />
  return (
    <div className={cn(res.loading && 'opacity-60')}>
      <DataGrid id={`grup.${group}`} columns={cols} rows={res.data.rows} rowKey={(r) => String(r.d0)} totals={res.data.totals
        ? Object.fromEntries(Object.entries(res.data.totals)) : null}
        toolbarLeft={toolbar}
        toolbarRight={<span className="flex items-center gap-1.5 text-[12.5px] text-muted">{res.data.row_count.toLocaleString('tr-TR')} grup
          <InfoTip>Bir satırın solundaki oka tıklayınca o grubun fatura satırları açılır.</InfoTip></span>}
        renderExpanded={(r) => (
          <div>
            <p className="mb-2 text-[13px] font-semibold">{fmtPeriodKey(r.d0, group)} — hareketler</p>
            <LinesView dir={dir} search={search} satis={satis} compact extraFilters={{ [group]: [String(r.d0)] }} />
          </div>
        )} />
    </div>
  )
}
