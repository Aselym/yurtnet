import { useEffect, useMemo, useState } from 'react'
import { ArrowDown, ArrowUp, Bookmark, Download, X } from 'lucide-react'
import { api, download, type Direction, type QueryResult } from '../lib/api'
import { useAsync, useLocal } from '../lib/hooks'
import { useWork } from '../lib/state'
import { PageHeader } from '../components/Shell'
import { FilterBar } from '../components/FilterBar'
import { DataGrid, type GridCol } from '../components/data/DataGrid'
import { BarChart, Legend, RankBars, SERIES } from '../components/charts/Charts'
import { Button, ErrorBox, InfoTip, Loading, Modal, Panel, Segmented, Select, cn, inputCls, toast } from '../components/ui'

interface Config {
  rows: string[]
  pivot: string | null
  measures: string[]
  direction: Direction
  view: 'table' | 'chart'
  heat: boolean
  limit: number
}

const ZAMAN = new Set(['day', 'week', 'month', 'quarter', 'year', 'weekday'])
const VARSAYILAN: Config = { rows: ['category'], pivot: 'quarter', measures: ['net_tl'], direction: 'SATIS_NET', view: 'table', heat: true, limit: 500 }

const HAZIR: { label: string; c: Partial<Config> }[] = [
  { label: 'Kategori × çeyrek satış', c: { rows: ['category'], pivot: 'quarter', measures: ['net_tl'] } },
  { label: 'Marka bazında kâr ve marj', c: { rows: ['brand'], pivot: null, measures: ['net_tl', 'profit_tl', 'margin', 'clients'] } },
  { label: 'Müşteri × ürün grubu', c: { rows: ['client', 'category'], pivot: null, measures: ['net_tl', 'qty'] } },
  { label: 'Temsilci × ay', c: { rows: ['salesman'], pivot: 'month', measures: ['net_tl'] } },
  { label: 'Depoda bekleme süresi', c: { rows: ['aging_bucket'], pivot: null, measures: ['net_tl', 'qty', 'margin', 'lines'] } },
  { label: 'Şehir × kategori', c: { rows: ['city'], pivot: 'category', measures: ['net_tl'] } },
  { label: 'Tedarikçi bazında alış', c: { rows: ['client'], pivot: 'year', measures: ['net_tl'], direction: 'ALIS_NET' } },
  { label: 'Haftanın günü', c: { rows: ['weekday'], pivot: null, measures: ['net_tl', 'invoices'] } },
]

export default function AnalysisPage({ params }: { params: URLSearchParams }) {
  const { base, meta } = useWork()
  const [cfg, setCfg] = useLocal<Config>('analiz.cfg', (() => {
    try { const p = params.get('c'); if (p) return { ...VARSAYILAN, ...JSON.parse(decodeURIComponent(p)) } } catch { /* yok */ }
    return VARSAYILAN
  })())
  const set = (p: Partial<Config>) => setCfg({ ...cfg, ...p })
  const dims = meta?.dimensions ?? []
  const measures = meta?.measures ?? []
  const dimLabel = (k: string) => dims.find((d) => d.key === k)?.label ?? k

  const req = { ...base, direction: cfg.direction, group_by: cfg.rows, pivot_by: cfg.pivot, measures: cfg.pivot ? cfg.measures.slice(0, 1) : cfg.measures, limit: cfg.limit }
  const res = useAsync(() => api.post<QueryResult>('/api/analiz/sorgu', req), [JSON.stringify(req)])
  const [saveOpen, setSaveOpen] = useState(false)

  const cols: GridCol[] = useMemo(() => (res.data?.columns ?? []).map((c) => ({
    key: c.key, label: c.label, type: c.type, dim: c.dim, heat: cfg.heat && c.type !== 'dim' && c.key !== '_total' && c.type !== 'pct',
    width: c.type === 'dim' ? 260 : undefined,
  })), [res.data, cfg.heat])

  return (
    <div>
      <PageHeader title="Analiz"
        subtitle="Satırları, kolonları ve ölçüleri siz seçin. Kurduğunuz görünümü kaydedip tekrar açabilir, Excel'e aktarabilirsiniz."
        actions={<>
          <SavedViews onLoad={(c) => setCfg({ ...VARSAYILAN, ...c })} />
          <Button icon={<Bookmark className="size-4" />} onClick={() => setSaveOpen(true)}>Görünümü kaydet</Button>
          <Button icon={<Download className="size-4" />} onClick={() => download('/api/export/sorgu', { request: req, title: 'Analiz', filename: 'Analiz' }).catch((e) => toast.err(e.message))}>
            Excel'e aktar
          </Button>
        </>}>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {HAZIR.map((h) => (
            <button key={h.label} onClick={() => setCfg({ ...VARSAYILAN, ...h.c })}
              className="h-7 rounded-full border border-line bg-surface px-3 text-[12.5px] text-ink-2 hover:border-line-strong hover:text-ink">{h.label}</button>
          ))}
        </div>
        <FilterBar />
      </PageHeader>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="panel flex flex-col gap-5 p-4 xl:sticky xl:top-[86px] xl:self-start">
          <div>
            <p className="mb-1.5 text-[13px] font-semibold">Hareket</p>
            <select value={cfg.direction} onChange={(e) => set({ direction: e.target.value as Direction })} className={inputCls}>
              {(meta?.directions ?? []).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </select>
          </div>

          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold">Satırlar <InfoTip>En fazla 4 kırılım. Sıra önemlidir: ilk kırılım en dıştaki gruptur.</InfoTip></p>
            <ol className="flex flex-col gap-1.5">
              {cfg.rows.map((r, i) => (
                <li key={r} className="flex items-center gap-1 rounded-lg border border-line bg-surface-2 py-1 pr-1 pl-2.5 text-[13px]">
                  <span className="flex-1 truncate">{dimLabel(r)}</span>
                  <button disabled={i === 0} onClick={() => { const a = [...cfg.rows];[a[i - 1], a[i]] = [a[i], a[i - 1]]; set({ rows: a }) }}
                    aria-label="Yukarı" className="rounded p-1 text-muted hover:text-ink disabled:opacity-30"><ArrowUp className="size-3.5" /></button>
                  <button disabled={i === cfg.rows.length - 1} onClick={() => { const a = [...cfg.rows];[a[i + 1], a[i]] = [a[i], a[i + 1]]; set({ rows: a }) }}
                    aria-label="Aşağı" className="rounded p-1 text-muted hover:text-ink disabled:opacity-30"><ArrowDown className="size-3.5" /></button>
                  <button onClick={() => set({ rows: cfg.rows.filter((x) => x !== r) })} aria-label="Kaldır" className="rounded p-1 text-muted hover:text-neg"><X className="size-3.5" /></button>
                </li>
              ))}
            </ol>
            {cfg.rows.length < 4 && (
              <select value="" onChange={(e) => e.target.value && set({ rows: [...cfg.rows, e.target.value] })} className={cn(inputCls, 'mt-1.5 text-ink-2')}>
                <option value="">+ Kırılım ekle</option>
                {dims.filter((d) => !cfg.rows.includes(d.key) && d.key !== cfg.pivot).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
              </select>
            )}
          </div>

          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold">Kolonlar <InfoTip>Bir boyut seçerseniz değerleri yan yana kolonlara açılır (pivot). Pivotta tek ölçü gösterilir.</InfoTip></p>
            <select value={cfg.pivot ?? ''} onChange={(e) => set({ pivot: e.target.value || null })} className={inputCls}>
              <option value="">Yok (ölçüler kolon olur)</option>
              {dims.filter((d) => !cfg.rows.includes(d.key)).map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </select>
          </div>

          <div>
            <p className="mb-1.5 text-[13px] font-semibold">Ölçüler {cfg.pivot && <span className="font-normal text-muted">(pivotta ilki)</span>}</p>
            <ul className="scroll-thin flex max-h-64 flex-col gap-0.5 overflow-auto">
              {measures.map((m) => {
                const on = cfg.measures.includes(m.key)
                const idx = cfg.measures.indexOf(m.key)
                return (
                  <li key={m.key}>
                    <label className={cn('flex cursor-pointer items-center gap-2 rounded-md px-1.5 py-1 text-[13px] hover:bg-surface-2', on && 'font-medium')}>
                      <input type="checkbox" checked={on} className="accent-[var(--brand)]"
                        onChange={() => set({ measures: on ? cfg.measures.filter((x) => x !== m.key) : [...cfg.measures, m.key] })} />
                      <span className="flex-1">{m.label}</span>
                      {on && cfg.measures.length > 1 && <span className="text-[11px] text-muted">{idx + 1}</span>}
                    </label>
                  </li>
                )
              })}
            </ul>
          </div>

          <div className="flex flex-col gap-2.5 border-t border-line pt-4">
            <Segmented value={cfg.view} onChange={(v) => set({ view: v })} options={[{ value: 'table', label: 'Tablo' }, { value: 'chart', label: 'Grafik' }]} />
            <label className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={cfg.heat} onChange={(e) => set({ heat: e.target.checked })} className="accent-[var(--brand)]" />
              Isı haritası (büyük değer koyu)
            </label>
            <Select label="Satır sınırı" value={String(cfg.limit)} onChange={(v) => set({ limit: Number(v) })} options={[
              { value: '25', label: 'İlk 25' }, { value: '100', label: 'İlk 100' }, { value: '500', label: 'İlk 500' }, { value: '0', label: 'Hepsi' },
            ]} />
          </div>
        </aside>

        <section className="min-w-0">
          {res.error && <ErrorBox message={res.error} onRetry={res.reload} />}
          {!res.data && res.loading && <Loading />}
          {res.data && cfg.measures.length === 0 && <Panel><p className="text-[13px] text-ink-2">En az bir ölçü seçin.</p></Panel>}
          {res.data && cfg.measures.length > 0 && (
            <div className={cn('flex flex-col gap-5', res.loading && 'opacity-60')}>
              {cfg.view === 'chart' && <ResultChart res={res.data} cfg={cfg} />}
              <div className="panel p-4">
                <DataGrid id={`analiz.${cfg.rows.join('-')}.${cfg.pivot}`} columns={cols} rows={res.data.rows}
                  rowKey={(r) => cfg.rows.map((_, i) => String(r[`d${i}`])).join('|') || 'toplam'}
                  totals={cfg.pivot ? Object.fromEntries(cols.filter((c) => c.type !== 'dim').map((c) => [c.key, res.data!.rows.reduce((s, r) => s + (Number(r[c.key]) || 0), 0)])) : res.data.totals}
                  maxHeight={680}
                  toolbarLeft={<span className="text-[13px] text-ink-2">
                    {res.data.row_count.toLocaleString('tr-TR')} satır{cfg.limit && res.data.row_count > cfg.limit ? `, ilk ${cfg.limit} gösteriliyor` : ''}
                  </span>} />
              </div>
            </div>
          )}
        </section>
      </div>
      <SaveModal open={saveOpen} onClose={() => setSaveOpen(false)} config={cfg} />
    </div>
  )
}

function ResultChart({ res, cfg }: { res: QueryResult; cfg: Config }) {
  const ilk = cfg.rows[0]
  const m = cfg.measures[0]
  const tip = res.columns.find((c) => c.measure === m)?.type ?? (res.pivot ? res.columns.find((c) => c.pivot)?.type : 'num') ?? 'num'
  if (!ilk) return null
  if (ZAMAN.has(ilk) && cfg.rows.length === 1) {
    const data = [...res.rows].sort((a, b) => String(a.d0).localeCompare(String(b.d0)))
    const series = res.pivot
      ? res.pivot.values.slice(0, 8).map((v, i) => ({ key: `p::${v}`, label: String(v), color: SERIES[i] }))
      : cfg.measures.slice(0, 1).map((k) => ({ key: `m_${k}`, label: res.columns.find((c) => c.measure === k)?.label ?? k }))
    return (
      <Panel title="Grafik" actions={<Legend series={series} />}>
        <BarChart data={data} xKey="d0" dim={ilk} type={tip} series={series} stacked />
      </Panel>
    )
  }
  const key = res.pivot ? '_total' : `m_${m}`
  return (
    <Panel title={`İlk 15 — ${res.columns.find((c) => c.key === key)?.label ?? ''}`}>
      <RankBars rows={[...res.rows].sort((a, b) => (Number(b[key]) || 0) - (Number(a[key]) || 0)).slice(0, 15)
        .map((r) => ({ ...r, _lbl: cfg.rows.map((_, i) => r[`d${i}`]).join(' / ') }))} labelKey="_lbl" valueKey={key} type={tip} />
    </Panel>
  )
}

function SaveModal({ open, onClose, config }: { open: boolean; onClose: () => void; config: Config }) {
  const [name, setName] = useState('')
  return (
    <Modal open={open} onClose={onClose} title="Görünümü kaydet" footer={<>
      <Button variant="ghost" onClick={onClose}>Vazgeç</Button>
      <Button variant="primary" disabled={!name.trim()} onClick={async () => {
        try {
          await api.post('/api/gorunumler', { name: name.trim(), page: 'analiz', config })
          toast.ok(`"${name.trim()}" kaydedildi.`)
          window.dispatchEvent(new Event('defter:views'))
          setName('')
          onClose()
        } catch (e) { toast.err(e instanceof Error ? e.message : 'Kaydedilemedi.') }
      }}>Kaydet</Button>
    </>}>
      <label className="flex flex-col gap-1.5 text-[13px]">
        Görünüm adı
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Örn. Aylık Dell satışları" className={inputCls} />
      </label>
      <p className="mt-2 text-[12.5px] text-muted">Satır, kolon ve ölçü seçimleri kaydedilir. Dönem ve filtreler üst çubuktan uygulanmaya devam eder.</p>
    </Modal>
  )
}

function SavedViews({ onLoad }: { onLoad: (c: Partial<Config>) => void }) {
  const [tick, setTick] = useState(0)
  const v = useAsync(() => api.get<{ id: number; name: string; config: Partial<Config> }[]>('/api/gorunumler?page=analiz'), [tick])
  useEffect(() => {
    const on = () => setTick((t) => t + 1)
    window.addEventListener('defter:views', on)
    return () => window.removeEventListener('defter:views', on)
  }, [])
  if (!v.data?.length) return null
  return (
    <select value="" onChange={(e) => { const s = v.data!.find((x) => String(x.id) === e.target.value); if (s) onLoad(s.config) }}
      className="h-9 rounded-[var(--radius-ctl)] border border-line-strong bg-surface px-3 text-sm">
      <option value="">Kayıtlı görünümler ({v.data.length})</option>
      {v.data.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
    </select>
  )
}

