import { useMemo, useRef, useState } from 'react'
import { CalendarRange, ChevronDown } from 'lucide-react'
import { api, type QueryResult } from '../lib/api'
import { fmtPeriodKey, fmtShort, rangeLabel } from '../lib/format'
import { useAsync } from '../lib/hooks'
import { iso, today, useWork } from '../lib/state'
import { Button, Popover, cn, inputCls } from './ui'

// Donem seridi: verinin tum gecmisi aylik cubuklar halinde; secili donem
// uzerinde turuncu bant. Surukleyerek ay araligi secilir. Secim tum
// sayfalara uygulanir.

function ayBasi(key: string) { return `${key}-01` }
function ayinSonu(key: string) {
  const [y, m] = key.split('-').map(Number)
  return iso(new Date(y, m, 0))
}
function aylar(first: string, last: string): string[] {
  const out: string[] = []
  let [y, m] = first.slice(0, 7).split('-').map(Number)
  const [ly, lm] = last.slice(0, 7).split('-').map(Number)
  while (y < ly || (y === ly && m <= lm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`)
    m += 1
    if (m > 12) { m = 1; y += 1 }
  }
  return out
}

export function presets(): { key: string; label: string; range: () => [string, string] }[] {
  const d = new Date()
  const y = d.getFullYear(), m = d.getMonth()
  const q = Math.floor(m / 3)
  return [
    { key: 'bu-ay', label: 'Bu ay', range: () => [iso(new Date(y, m, 1)), today()] },
    { key: 'gecen-ay', label: 'Geçen ay', range: () => [iso(new Date(y, m - 1, 1)), iso(new Date(y, m, 0))] },
    { key: 'bu-ceyrek', label: 'Bu çeyrek', range: () => [iso(new Date(y, q * 3, 1)), today()] },
    { key: 'gecen-ceyrek', label: 'Geçen çeyrek', range: () => [iso(new Date(y, q * 3 - 3, 1)), iso(new Date(y, q * 3, 0))] },
    { key: 'ytd', label: 'Yılbaşından bugüne', range: () => [iso(new Date(y, 0, 1)), today()] },
    { key: 'son-30', label: 'Son 30 gün', range: () => [iso(new Date(y, m, d.getDate() - 29)), today()] },
    { key: 'son-90', label: 'Son 90 gün', range: () => [iso(new Date(y, m, d.getDate() - 89)), today()] },
    { key: 'son-12', label: 'Son 12 ay', range: () => [iso(new Date(y - 1, m, d.getDate() + 1)), today()] },
    { key: 'gecen-yil', label: 'Geçen yıl', range: () => [iso(new Date(y - 1, 0, 1)), iso(new Date(y - 1, 11, 31))] },
  ]
}

export function PeriodStrip() {
  const { from, to, setPeriod, meta, filters } = useWork()
  const first = meta?.data.first
  const last = meta?.data.last
  const hist = useAsync<QueryResult | null>(
    () => first && last
      ? api.post<QueryResult>('/api/analiz/sorgu', {
        date_from: first, date_to: last, filters, direction: 'SATIS_NET', group_by: ['month'], measures: ['net_tl'],
      })
      : Promise.resolve(null),
    [first, last, JSON.stringify(filters)],
  )

  const months = useMemo(() => (first && last ? aylar(first, last > today() ? last : today()) : []), [first, last])
  const values = useMemo(() => {
    const map = new Map<string, number>()
    hist.data?.rows.forEach((r) => map.set(String(r.d0), Number(r.m_net_tl) || 0))
    return months.map((k) => map.get(k) ?? 0)
  }, [hist.data, months])
  const max = Math.max(1, ...values)

  const svgRef = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<{ a: number; b: number } | null>(null)
  const [hover, setHover] = useState<number | null>(null)

  const W = 1000, H = 44
  const n = months.length || 1
  const bw = W / n
  const idx = (clientX: number) => {
    const r = svgRef.current!.getBoundingClientRect()
    return Math.max(0, Math.min(n - 1, Math.floor(((clientX - r.left) / r.width) * n)))
  }
  const selA = months.findIndex((k) => ayinSonu(k) >= from)
  const selBraw = months.findIndex((k) => ayBasi(k) > to)
  const selB = selBraw === -1 ? n - 1 : selBraw - 1
  const band = drag ? [Math.min(drag.a, drag.b), Math.max(drag.a, drag.b)] : [selA, selB]

  const finish = () => {
    if (!drag) return
    const a = Math.min(drag.a, drag.b), b = Math.max(drag.a, drag.b)
    const end = ayinSonu(months[b])
    setPeriod(ayBasi(months[a]), end > today() ? today() : end)
    setDrag(null)
  }

  return (
    <div className="flex min-w-0 flex-1 items-center gap-3 max-md:flex-none">
      <PeriodMenu />
      <div className="relative hidden h-[52px] min-w-[220px] flex-1 md:block">
        {months.length > 0 && (
          <svg
            ref={svgRef}
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
            className="h-[44px] w-full cursor-crosshair select-none"
            role="slider"
            aria-label="Dönem seçici: sürükleyerek ay aralığı seçin"
            aria-valuetext={rangeLabel(from, to)}
            onMouseDown={(e) => { const i = idx(e.clientX); setDrag({ a: i, b: i }) }}
            onMouseMove={(e) => { const i = idx(e.clientX); setHover(i); if (drag) setDrag({ ...drag, b: i }) }}
            onMouseUp={finish}
            onMouseLeave={() => { setHover(null); finish() }}
          >
            {band[0] >= 0 && (
              <rect x={band[0] * bw} y={0} width={(band[1] - band[0] + 1) * bw} height={H}
                fill="var(--brand)" opacity={0.12} rx={1} />
            )}
            {values.map((v, i) => {
              const h = Math.max(1.5, (v / max) * (H - 8))
              const inSel = i >= band[0] && i <= band[1]
              return (
                <rect key={months[i]} x={i * bw + bw * 0.18} y={H - h} width={Math.max(1, bw * 0.64)} height={h}
                  rx={Math.min(1, bw * 0.3)}
                  fill={inSel ? 'var(--brand)' : 'var(--line-strong)'} opacity={hover === i ? 1 : inSel ? 0.9 : 0.75} />
              )
            })}
          </svg>
        )}
        {hover !== null && months[hover] && (
          <div className="pointer-events-none absolute -bottom-6 z-30 -translate-x-1/2 rounded-[var(--radius-ctl)] border border-line bg-surface px-2 py-0.5 text-[11.5px] whitespace-nowrap text-ink-2 shadow-sm"
            style={{ left: `${((hover + 0.5) / n) * 100}%` }}>
            {fmtPeriodKey(months[hover], 'month')} <span className="tnum text-ink">{fmtShort(values[hover], 'tl')}</span>
          </div>
        )}
        <div className="flex justify-between text-[10.5px] text-muted">
          <span>{months[0]?.slice(0, 4)}</span>
          <span>{months[months.length - 1]?.slice(0, 4)}</span>
        </div>
      </div>
    </div>
  )
}

function PeriodMenu() {
  const { from, to, setPeriod, meta } = useWork()
  const [f, setF] = useState(from)
  const [t, setT] = useState(to)
  return (
    <Popover
      width={320}
      trigger={(open, toggle) => (
        <button
          onClick={() => { setF(from); setT(to); toggle() }}
          className={cn('flex h-10 shrink-0 items-center gap-2 rounded-[var(--radius-ctl)] border bg-surface px-3 text-left transition-colors',
            open ? 'border-brand' : 'border-line-strong hover:border-ink-2')}
        >
          <CalendarRange className="size-4 text-brand" />
          <span className="flex flex-col leading-tight">
            <span className="text-[11px] text-muted">Dönem</span>
            <span className="text-[13.5px] font-semibold whitespace-nowrap text-ink">{rangeLabel(from, to)}</span>
          </span>
          <ChevronDown className="size-4 text-muted" />
        </button>
      )}
    >
      {(close) => (
        <div className="p-2">
          <ul className="grid grid-cols-2 gap-0.5">
            {presets().map((p) => (
              <li key={p.key}>
                <button onClick={() => { const [a, b] = p.range(); setPeriod(a, b); close() }}
                  className="w-full rounded-[var(--radius-ctl)] px-2.5 py-1.5 text-left text-[13px] hover:bg-surface-2">{p.label}</button>
              </li>
            ))}
            {meta?.data.first && (
              <li>
                <button onClick={() => { setPeriod(meta.data.first!, today()); close() }}
                  className="w-full rounded-[var(--radius-ctl)] px-2.5 py-1.5 text-left text-[13px] hover:bg-surface-2">Tüm veri</button>
              </li>
            )}
          </ul>
          <div className="mt-2 border-t border-line px-1.5 pt-3 pb-1">
            <p className="mb-2 text-[12px] text-muted">Özel aralık</p>
            <div className="flex items-center gap-2">
              <input type="date" value={f} onChange={(e) => setF(e.target.value)} className={inputCls} />
              <span className="text-muted">–</span>
              <input type="date" value={t} onChange={(e) => setT(e.target.value)} className={inputCls} />
            </div>
            <Button variant="primary" size="sm" className="mt-2.5 w-full" disabled={!f || !t}
              onClick={() => { setPeriod(f, t); close() }}>Uygula</Button>
          </div>
        </div>
      )}
    </Popover>
  )
}
