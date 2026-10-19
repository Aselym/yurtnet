import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { ColType } from '../../lib/api'
import { fmt, fmtAxis, fmtPeriodKey, fmtShort, niceTicks } from '../../lib/format'
import { cn } from '../ui'

// Dataviz kurallari: tek eksen; ince isaretler, veri ucunda 4px yuvarlak,
// yigilmis dilimler arasinda 2px zemin boslugu; silik izgara; kategorik
// renkler sabit sirayla (renk siraya degil varliga bagli); 2+ seride lejant.

export const SERIES = ['var(--s1)', 'var(--s2)', 'var(--s3)', 'var(--s4)', 'var(--s5)', 'var(--s6)', 'var(--s7)', 'var(--s8)']

function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [w, setW] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e.contentRect.width)))
    ro.observe(ref.current)
    setW(ref.current.clientWidth)
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}


export interface Series { key: string; label: string; color?: string }

interface Tip { x: number; y: number; content: ReactNode }

function Tooltip({ tip }: { tip: Tip | null }) {
  if (!tip) return null
  return (
    <div className="pointer-events-none absolute z-20 min-w-[160px] -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-lg border border-line bg-surface px-3 py-2 text-[12.5px] shadow-[0_10px_30px_rgba(20,33,28,.16)]"
      style={{ left: tip.x, top: tip.y }}>
      {tip.content}
    </div>
  )
}

export function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-2">
      {series.map((s, i) => (
        <span key={s.key} className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px]" style={{ background: s.color ?? SERIES[i] }} />
          {s.label}
        </span>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ zaman serisi cubuk
export function BarChart({ data, xKey, series, type = 'tl', dim, height = 240, stacked = true, onBarClick, emptyText }: {
  data: Record<string, unknown>[]; xKey: string; series: Series[]; type?: ColType; dim?: string; height?: number
  stacked?: boolean; onBarClick?: (row: Record<string, unknown>) => void; emptyText?: string
}) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [tip, setTip] = useState<Tip | null>(null)
  const [hi, setHi] = useState<number | null>(null)
  const L = 92, R = 8, T = 10, B = 26
  const iw = Math.max(0, w - L - R), ih = height - T - B

  const totals = data.map((r) => series.reduce((s, se) => s + Math.max(0, Number(r[se.key]) || 0), 0))
  const ticks = niceTicks(stacked ? Math.max(0, ...totals) : Math.max(0, ...data.flatMap((r) => series.map((s) => Number(r[s.key]) || 0))))
  const maxV = ticks[ticks.length - 1] || 1
  const n = data.length || 1
  const slot = iw / n
  const groupW = Math.min(56, slot * 0.72)
  const barW = stacked ? groupW : Math.max(2, (groupW - (series.length - 1) * 2) / series.length)
  const y = (v: number) => T + ih - (v / maxV) * ih
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(iw / 58))))

  if (data.length === 0) return <div className="py-16 text-center text-[13px] text-muted">{emptyText || 'Bu dönemde veri yok.'}</div>

  return (
    <div ref={ref} className="relative w-full">
      <svg width={w} height={height} role="img" aria-label="Zaman serisi grafiği" onMouseLeave={() => { setTip(null); setHi(null) }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={L + iw} y1={y(t)} y2={y(t)} stroke={t === 0 ? 'var(--chart-axis)' : 'var(--chart-grid)'} strokeWidth={1} />
            <text x={L - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" className="tnum">{fmtAxis(t, type)}</text>
          </g>
        ))}
        {data.map((r, i) => {
          const cx = L + slot * i + slot / 2
          let acc = 0
          return (
            <g key={String(r[xKey])} opacity={hi === null || hi === i ? 1 : 0.55}>
              {series.map((s, j) => {
                const v = Math.max(0, Number(r[s.key]) || 0)
                if (!v) return null
                let x0: number, yTop: number, hgt: number
                if (stacked) {
                  x0 = cx - barW / 2
                  yTop = y(acc + v)
                  hgt = y(acc) - y(acc + v) - (acc > 0 ? 2 : 0)
                  acc += v
                } else {
                  x0 = cx - groupW / 2 + j * (barW + 2)
                  yTop = y(v)
                  hgt = y(0) - y(v)
                }
                const top = stacked ? j === series.length - 1 || series.slice(j + 1).every((s2) => !(Number(r[s2.key]) > 0)) : true
                const rr = Math.min(4, barW / 2, Math.max(0, hgt))
                return (
                  <path key={s.key} fill={s.color ?? SERIES[j]}
                    d={top
                      ? `M${x0},${yTop + hgt} V${yTop + rr} Q${x0},${yTop} ${x0 + rr},${yTop} H${x0 + barW - rr} Q${x0 + barW},${yTop} ${x0 + barW},${yTop + rr} V${yTop + hgt} Z`
                      : `M${x0},${yTop + hgt} V${yTop} H${x0 + barW} V${yTop + hgt} Z`} />
                )
              })}
              {i % labelEvery === 0 && (
                <text x={cx} y={height - 8} textAnchor="middle" fontSize={11} fill="var(--muted)">{fmtPeriodKey(r[xKey], dim)}</text>
              )}
              <rect x={L + slot * i} y={T} width={slot} height={ih} fill="transparent"
                className={cn(onBarClick && 'cursor-pointer')}
                onClick={() => onBarClick?.(r)}
                onMouseMove={() => {
                  setHi(i)
                  setTip({
                    x: cx, y: y(stacked ? totals[i] : Math.max(...series.map((s) => Number(r[s.key]) || 0))),
                    content: (
                      <div>
                        <p className="mb-1 font-semibold text-ink">{fmtPeriodKey(r[xKey], dim)}</p>
                        {series.map((s, j) => (
                          <p key={s.key} className="flex items-center justify-between gap-4 text-ink-2">
                            <span className="inline-flex items-center gap-1.5">
                              <span className="inline-block size-2 rounded-[2px]" style={{ background: s.color ?? SERIES[j] }} />{s.label}
                            </span>
                            <span className="tnum text-ink">{fmt(r[s.key], type)}</span>
                          </p>
                        ))}
                        {stacked && series.length > 1 && (
                          <p className="mt-1 flex justify-between gap-4 border-t border-line pt-1 font-medium text-ink">
                            <span>Toplam</span><span className="tnum">{fmt(totals[i], type)}</span>
                          </p>
                        )}
                        {onBarClick && <p className="mt-1.5 text-[11.5px] text-muted">Ayrıntı için tıklayın</p>}
                      </div>
                    ),
                  })
                }} />
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tip} />
    </div>
  )
}

// ------------------------------------------------------------------ cizgi
export function LineChart({ data, xKey, series, type = 'tl', dim, height = 240 }: {
  data: Record<string, unknown>[]; xKey: string; series: Series[]; type?: ColType; dim?: string; height?: number
}) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hi, setHi] = useState<number | null>(null)
  const L = 92, R = 12, T = 10, B = 26
  const iw = Math.max(0, w - L - R), ih = height - T - B
  const ticks = niceTicks(Math.max(0, ...data.flatMap((r) => series.map((s) => Number(r[s.key]) || 0))))
  const maxV = ticks[ticks.length - 1] || 1
  const n = data.length
  const x = (i: number) => L + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw)
  const y = (v: number) => T + ih - (v / maxV) * ih
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(iw / 58))))
  if (!n) return <div className="py-16 text-center text-[13px] text-muted">Bu dönemde veri yok.</div>
  return (
    <div ref={ref} className="relative w-full">
      <svg width={w} height={height} role="img" aria-label="Çizgi grafiği"
        onMouseMove={(e) => {
          const r = (e.currentTarget as SVGSVGElement).getBoundingClientRect()
          const px = e.clientX - r.left - L
          setHi(Math.max(0, Math.min(n - 1, Math.round((px / iw) * (n - 1)))))
        }}
        onMouseLeave={() => setHi(null)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={L} x2={L + iw} y1={y(t)} y2={y(t)} stroke={t === 0 ? 'var(--chart-axis)' : 'var(--chart-grid)'} />
            <text x={L - 8} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--muted)" className="tnum">{fmtAxis(t, type)}</text>
          </g>
        ))}
        {data.map((r, i) => i % labelEvery === 0 && (
          <text key={i} x={x(i)} y={height - 8} textAnchor="middle" fontSize={11} fill="var(--muted)">{fmtPeriodKey(r[xKey], dim)}</text>
        ))}
        {series.map((s, j) => (
          <path key={s.key} fill="none" stroke={s.color ?? SERIES[j]} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round"
            d={data.map((r, i) => `${i ? 'L' : 'M'}${x(i)},${y(Number(r[s.key]) || 0)}`).join(' ')} />
        ))}
        {hi !== null && (
          <g>
            <line x1={x(hi)} x2={x(hi)} y1={T} y2={T + ih} stroke="var(--line-strong)" strokeDasharray="3 3" />
            {series.map((s, j) => (
              <circle key={s.key} cx={x(hi)} cy={y(Number(data[hi][s.key]) || 0)} r={4.5} fill={s.color ?? SERIES[j]}
                stroke="var(--surface)" strokeWidth={2} />
            ))}
          </g>
        )}
      </svg>
      {hi !== null && (
        <Tooltip tip={{
          x: x(hi), y: y(Math.max(...series.map((s) => Number(data[hi][s.key]) || 0))),
          content: (
            <div>
              <p className="mb-1 font-semibold text-ink">{fmtPeriodKey(data[hi][xKey], dim)}</p>
              {series.map((s, j) => (
                <p key={s.key} className="flex justify-between gap-4 text-ink-2">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="inline-block h-0.5 w-3 rounded" style={{ background: s.color ?? SERIES[j] }} />{s.label}
                  </span>
                  <span className="tnum text-ink">{fmt(data[hi][s.key], type)}</span>
                </p>
              ))}
            </div>
          ),
        }} />
      )}
    </div>
  )
}

// ------------------------------------------------------------------ sirali yatay cubuk listesi
export function RankBars({ rows, labelKey, valueKey, type = 'tl', sub, onClick, color = 'var(--s1)', max }: {
  rows: Record<string, unknown>[]; labelKey: string; valueKey: string; type?: ColType
  sub?: (r: Record<string, unknown>) => ReactNode; onClick?: (r: Record<string, unknown>) => void; color?: string; max?: number
}) {
  const top = max ?? Math.max(0, ...rows.map((r) => Number(r[valueKey]) || 0))
  if (!rows.length) return <p className="py-6 text-center text-[13px] text-muted">Veri yok.</p>
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r, i) => {
        const v = Number(r[valueKey]) || 0
        return (
          <li key={String(r[labelKey]) + i}>
            <button onClick={() => onClick?.(r)} disabled={!onClick}
              className={cn('group block w-full text-left', onClick && 'cursor-pointer')}>
              <div className="flex items-baseline justify-between gap-3 text-[13px]">
                <span className={cn('min-w-0 truncate text-ink', onClick && 'group-hover:underline')}>{String(r[labelKey])}</span>
                <span className="tnum shrink-0 font-medium text-ink">{fmtShort(v, type)}</span>
              </div>
              <div className="mt-1 h-1.5 w-full rounded-full bg-surface-3">
                <div className="h-full rounded-full" style={{ width: `${top ? Math.max(1.5, (v / top) * 100) : 0}%`, background: color }} />
              </div>
              {sub && <div className="mt-0.5 text-[11.5px] text-muted">{sub(r)}</div>}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export function useSeriesFromPivot(result: { rows: Record<string, unknown>[]; pivot?: { values: string[] } } | null) {
  return useMemo(() => {
    if (!result?.pivot) return { data: [] as Record<string, unknown>[], series: [] as Series[] }
    const series = result.pivot.values.map((v, i) => ({ key: `p::${v}`, label: v, color: SERIES[i % 8] }))
    const data = [...result.rows].sort((a, b) => String(a.d0).localeCompare(String(b.d0)))
    return { data, series }
  }, [result])
}

export function useMounted() {
  const [m, setM] = useState(false)
  useEffect(() => setM(true), [])
  return m
}
