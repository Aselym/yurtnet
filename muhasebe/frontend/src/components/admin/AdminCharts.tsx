import { useRef, useState } from 'react'
import type { MouseEvent, ReactNode } from 'react'
import { CheckCircle2, Clock, XCircle } from 'lucide-react'
import { Card } from '@/components/ui/card'
import type { Offer, Sale, Subscription } from '@/lib/api'
import { getOfferFunnel, getRevenueHistory, getSubscriptionHealth } from '@/lib/adminAnalytics'
import { getRevenueForecast } from '@/lib/licenseAnalytics'

const GRID = '#e1e0d9'
const GRID_DARK = '#2c2c2a'
const BRAND = '#f2691f'

// Dataviz skill rezerve durum paleti (references/palette.md) — kategorik
// paletten ayrı, açık/koyu temada aynı adımlar, hiç değişmez.
const STATUS_GOOD = '#0ca30c'
const STATUS_WARNING = '#fab219'
const STATUS_CRITICAL = '#d03b3b'

interface TooltipState {
  x: number
  y: number
  content: ReactNode
}

function useChartTooltip() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  function show(e: MouseEvent, content: ReactNode) {
    const container = containerRef.current
    if (!container) return
    const containerRect = container.getBoundingClientRect()
    const targetRect = e.currentTarget.getBoundingClientRect()
    setTooltip({
      x: targetRect.left + targetRect.width / 2 - containerRect.left,
      y: targetRect.top - containerRect.top,
      content,
    })
  }

  function hide() {
    setTooltip(null)
  }

  return { containerRef, tooltip, show, hide }
}

function ChartTooltip({ tooltip }: { tooltip: TooltipState | null }) {
  if (!tooltip) return null
  return (
    <div
      className="pointer-events-none absolute z-10 min-w-max -translate-x-1/2 -translate-y-[calc(100%+8px)] rounded-lg border border-black/10 bg-white/95 px-3 py-2 text-xs leading-snug shadow-lg backdrop-blur-sm dark:border-white/10 dark:bg-neutral-900/95"
      style={{ left: tooltip.x, top: tooltip.y }}
    >
      {tooltip.content}
    </div>
  )
}

interface RevenueTrendChartProps {
  sales: Sale[]
}

export function RevenueTrendChart({ sales }: RevenueTrendChartProps) {
  const history = getRevenueHistory(sales, 6)
  const forecast = getRevenueForecast(sales, 3)
  const points = [
    ...history.map((b) => ({ ...b, isForecast: false })),
    ...forecast.map((b) => ({ ...b, isForecast: true })),
  ]
  const { containerRef, tooltip, show, hide } = useChartTooltip()

  const totalHistory = history.reduce((sum, b) => sum + b.revenue, 0)
  const totalForecast = forecast.reduce((sum, b) => sum + b.revenue, 0)
  const missingPrice = points.reduce((sum, b) => sum + b.missingPrice, 0)

  if (totalHistory === 0 && totalForecast === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">Gelir Trendi</h3>
        <p className="text-sm text-black/50 dark:text-white/50">Henüz fiyat bilgisi içeren satış kaydı yok.</p>
      </Card>
    )
  }

  const width = 640
  const height = 240
  const bottom = 180
  const top = 20
  const plotHeight = bottom - top
  const n = points.length
  const max = Math.max(1, ...points.map((p) => p.revenue))
  const xAt = (i: number) => (n <= 1 ? width / 2 : (i / (n - 1)) * width)
  const yAt = (v: number) => bottom - (v / max) * plotHeight

  const historyCount = history.length
  const pathFor = (slice: typeof points, offset: number) =>
    slice.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(offset + i)} ${yAt(p.revenue)}`).join(' ')
  const historyPath = pathFor(points.slice(0, historyCount), 0)
  const forecastPath = pathFor(points.slice(Math.max(historyCount - 1, 0)), Math.max(historyCount - 1, 0))
  const areaPath = `${pathFor(points, 0)} L ${xAt(n - 1)} ${bottom} L ${xAt(0)} ${bottom} Z`
  const todayX = historyCount > 0 && historyCount < n ? (xAt(historyCount - 1) + xAt(historyCount)) / 2 : xAt(n - 1)

  return (
    <Card className="p-5">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-black/70 dark:text-white/70">Gelir Trendi</h3>
        <div className="flex items-center gap-3 text-xs text-black/50 dark:text-white/50">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: BRAND }} />
            Gerçekleşen
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded-full" style={{ background: BRAND, opacity: 0.5 }} />
            Tahmini
          </span>
        </div>
      </div>
      <p className="mb-4 text-2xl font-semibold text-black/90 dark:text-white">
        {totalHistory.toLocaleString('tr-TR')} TRY{' '}
        <span className="text-sm font-normal text-black/40 dark:text-white/40">son 6 ayda gerçekleşen</span>
      </p>
      <div ref={containerRef} className="relative">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height={height}
          role="img"
          aria-label="Gelir trendi: geçmiş 6 ay ve önümüzdeki 3 ay tahmini"
        >
          <line x1={0} y1={bottom} x2={width} y2={bottom} stroke={GRID} strokeWidth={1} className="dark:hidden" />
          <line
            x1={0}
            y1={bottom}
            x2={width}
            y2={bottom}
            stroke={GRID_DARK}
            strokeWidth={1}
            className="hidden dark:block"
          />
          {historyCount > 0 && historyCount < n && (
            <>
              <line
                x1={todayX}
                y1={top}
                x2={todayX}
                y2={bottom}
                stroke={GRID}
                strokeWidth={1}
                strokeDasharray="3 3"
                className="dark:hidden"
              />
              <line
                x1={todayX}
                y1={top}
                x2={todayX}
                y2={bottom}
                stroke={GRID_DARK}
                strokeWidth={1}
                strokeDasharray="3 3"
                className="hidden dark:block"
              />
              <text
                x={todayX}
                y={top - 6}
                textAnchor="middle"
                fontSize={10}
                className="fill-current text-black/40 dark:text-white/40"
              >
                Bugün
              </text>
            </>
          )}
          <path d={areaPath} fill={BRAND} opacity={0.08} />
          <path d={historyPath} fill="none" stroke={BRAND} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
          <path
            d={forecastPath}
            fill="none"
            stroke={BRAND}
            strokeWidth={2}
            strokeDasharray="5 4"
            strokeLinecap="round"
            strokeLinejoin="round"
            opacity={0.55}
          />
          {points.map((p, i) => (
            <circle
              key={p.key}
              cx={xAt(i)}
              cy={yAt(p.revenue)}
              r={4}
              fill={p.isForecast ? 'white' : BRAND}
              stroke={BRAND}
              strokeWidth={2}
              className="cursor-pointer"
              onMouseEnter={(e) =>
                show(
                  e,
                  <>
                    <p className="font-semibold text-black/90 dark:text-white">
                      {p.label}
                      {p.isForecast ? ' (tahmini)' : ''}
                    </p>
                    <p className="text-black/60 dark:text-white/60">{p.revenue.toLocaleString('tr-TR')} TRY</p>
                    {p.missingPrice > 0 && (
                      <p className="text-black/40 dark:text-white/40">{p.missingPrice} kayıtta fiyat yok</p>
                    )}
                  </>
                )
              }
              onMouseLeave={hide}
            />
          ))}
          {points.map((p, i) => (
            <text
              key={`${p.key}-label`}
              x={xAt(i)}
              y={bottom + 18}
              textAnchor="middle"
              fontSize={11}
              className="fill-current text-black/40 dark:text-white/40"
            >
              {p.label}
            </text>
          ))}
        </svg>
        <ChartTooltip tooltip={tooltip} />
      </div>
      <p className="mt-3 text-xs text-black/50 dark:text-white/50">
        Önümüzdeki 3 ay için beklenen yenileme geliri:{' '}
        <span className="font-medium text-black/70 dark:text-white/70">
          {totalForecast.toLocaleString('tr-TR')} TRY
        </span>
        {missingPrice > 0 && <> · {missingPrice} kayıtta fiyat bilgisi yok, toplama dahil edilmedi.</>}
      </p>
    </Card>
  )
}

interface SubscriptionHealthDonutProps {
  subscriptions: Subscription[]
}

export function SubscriptionHealthDonut({ subscriptions }: SubscriptionHealthDonutProps) {
  const health = getSubscriptionHealth(subscriptions)
  const { containerRef, tooltip, show, hide } = useChartTooltip()

  if (health.total === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">Abonelik Sağlığı</h3>
        <p className="text-sm text-black/50 dark:text-white/50">Henüz abonelik verisi yok.</p>
      </Card>
    )
  }

  const legend = [
    { label: 'Aktif', value: health.active, color: STATUS_GOOD },
    { label: 'Risk Altında', value: health.atRisk, color: STATUS_WARNING },
    { label: 'Kayıp', value: health.lost, color: STATUS_CRITICAL },
  ]
  const segments = legend.filter((s) => s.value > 0)

  const size = 200
  const r = 70
  const strokeWidth = 24
  const circumference = 2 * Math.PI * r

  let acc = 0
  const segmentsWithOffset = segments.map((s) => {
    const fraction = s.value / health.total
    const length = fraction * circumference
    const offset = acc
    acc += length
    const gap = segments.length > 1 ? 2 : 0
    return { ...s, fraction, offset, dashArray: `${Math.max(length - gap, 0)} ${circumference - Math.max(length - gap, 0)}` }
  })

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">Abonelik Sağlığı</h3>
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-around">
        <div ref={containerRef} className="relative shrink-0">
          <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} role="img" aria-label="Abonelik sağlık dağılımı">
            <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={GRID} strokeWidth={strokeWidth} className="dark:hidden" />
            <circle
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={GRID_DARK}
              strokeWidth={strokeWidth}
              className="hidden dark:block"
            />
            {segmentsWithOffset.map((s) => (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={strokeWidth}
                strokeDasharray={s.dashArray}
                strokeDashoffset={-s.offset}
                strokeLinecap="round"
                transform={`rotate(-90 ${size / 2} ${size / 2})`}
                className="cursor-pointer transition-opacity hover:opacity-80"
                onMouseEnter={(e) =>
                  show(
                    e,
                    <>
                      <p className="font-semibold text-black/90 dark:text-white">{s.label}</p>
                      <p className="text-black/60 dark:text-white/60">
                        {s.value} abonelik (%{Math.round(s.fraction * 100)})
                      </p>
                    </>
                  )
                }
                onMouseLeave={hide}
              />
            ))}
            <text
              x={size / 2}
              y={size / 2 - 4}
              textAnchor="middle"
              fontSize={26}
              fontWeight={700}
              className="fill-current text-black/90 dark:text-white"
            >
              {health.total}
            </text>
            <text
              x={size / 2}
              y={size / 2 + 16}
              textAnchor="middle"
              fontSize={11}
              className="fill-current text-black/40 dark:text-white/40"
            >
              abonelik
            </text>
          </svg>
          <ChartTooltip tooltip={tooltip} />
        </div>
        <div className="w-full max-w-56 space-y-2">
          {legend.map((s) => (
            <div key={s.label} className="flex items-center gap-2 text-sm">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
              <span className="text-black/70 dark:text-white/70">{s.label}</span>
              <span className="ml-auto font-medium text-black/90 dark:text-white">{s.value}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

export interface RankedBarDatum {
  label: string
  value: number
  sublabel?: string
}

interface RankedBarChartProps {
  title: string
  data: RankedBarDatum[]
  color?: string
  emptyMessage?: string
  valueFormatter?: (v: number) => string
}

export function RankedBarChart({
  title,
  data,
  color = BRAND,
  emptyMessage = 'Veri yok.',
  valueFormatter,
}: RankedBarChartProps) {
  const { containerRef, tooltip, show, hide } = useChartTooltip()

  if (data.length === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">{title}</h3>
        <p className="text-sm text-black/50 dark:text-white/50">{emptyMessage}</p>
      </Card>
    )
  }

  const max = Math.max(1, ...data.map((d) => d.value))
  const rowHeight = 34
  const barMaxWidth = 300
  const labelWidth = 140
  const chartWidth = labelWidth + barMaxWidth + 50
  const height = data.length * rowHeight + 12
  const format = valueFormatter ?? ((v: number) => String(v))

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">{title}</h3>
      <div ref={containerRef} className="relative">
        <svg viewBox={`0 0 ${chartWidth} ${height}`} width="100%" height={height} role="img" aria-label={title}>
          {data.map((d, i) => {
            const y = i * rowHeight + 6
            const w = (d.value / max) * barMaxWidth
            return (
              <g key={d.label}>
                <text x={0} y={y + 15} fontSize={12} className="fill-current text-black/60 dark:text-white/60">
                  {d.label.length > 20 ? `${d.label.slice(0, 19)}…` : d.label}
                </text>
                <rect
                  x={labelWidth}
                  y={y + 4}
                  width={barMaxWidth}
                  height={18}
                  rx={4}
                  className="fill-current text-black/[0.03] dark:text-white/[0.05]"
                />
                {d.value > 0 && (
                  <rect
                    x={labelWidth}
                    y={y + 4}
                    width={Math.max(w, 4)}
                    height={18}
                    rx={4}
                    fill={color}
                    className="cursor-pointer"
                    onMouseEnter={(e) =>
                      show(
                        e,
                        <>
                          <p className="font-semibold text-black/90 dark:text-white">{d.label}</p>
                          <p className="text-black/60 dark:text-white/60">{format(d.value)}</p>
                          {d.sublabel && <p className="text-black/40 dark:text-white/40">{d.sublabel}</p>}
                        </>
                      )
                    }
                    onMouseLeave={hide}
                  />
                )}
                <text
                  x={labelWidth + barMaxWidth + 10}
                  y={y + 17}
                  fontSize={12}
                  fontWeight={600}
                  className="fill-current text-black/70 dark:text-white/70"
                >
                  {format(d.value)}
                </text>
              </g>
            )
          })}
        </svg>
        <ChartTooltip tooltip={tooltip} />
      </div>
    </Card>
  )
}

interface OfferFunnelChartProps {
  offers: Offer[]
}

export function OfferFunnelChart({ offers }: OfferFunnelChartProps) {
  const funnel = getOfferFunnel(offers)
  const total = funnel.pending + funnel.accepted + funnel.rejected

  if (total === 0) {
    return (
      <Card className="p-5">
        <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">Teklif Hunisi</h3>
        <p className="text-sm text-black/50 dark:text-white/50">Henüz teklif kaydı yok.</p>
      </Card>
    )
  }

  const rows = [
    { label: 'Beklemede', value: funnel.pending, color: BRAND, Icon: Clock },
    { label: 'Kazanılan', value: funnel.accepted, color: STATUS_GOOD, Icon: CheckCircle2 },
    { label: 'Kaybedilen', value: funnel.rejected, color: STATUS_CRITICAL, Icon: XCircle },
  ]
  const max = Math.max(1, ...rows.map((r) => r.value))

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">Teklif Hunisi</h3>
      <div className="space-y-3">
        {rows.map((r) => (
          <div key={r.label} className="flex items-center gap-3">
            <r.Icon className="h-4 w-4 shrink-0" style={{ color: r.color }} strokeWidth={1.75} />
            <span className="w-24 shrink-0 text-sm text-black/70 dark:text-white/70">{r.label}</span>
            <div className="h-4 flex-1 overflow-hidden rounded-full bg-black/[0.03] dark:bg-white/[0.05]">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${r.value > 0 ? Math.max((r.value / max) * 100, 4) : 0}%`,
                  background: r.color,
                }}
              />
            </div>
            <span className="w-8 shrink-0 text-right text-sm font-semibold text-black/90 dark:text-white">
              {r.value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-black/5 pt-3 text-xs text-black/50 dark:border-white/10 dark:text-white/50">
        <span>
          {funnel.winRate !== null
            ? `Kazanma oranı: %${funnel.winRate} (${funnel.accepted}/${funnel.accepted + funnel.rejected})`
            : 'Henüz karara bağlanmış teklif yok.'}
        </span>
        {funnel.pendingPipelineValue > 0 && (
          <span>
            Bekleyen teklif hattı:{' '}
            <span className="font-medium text-black/70 dark:text-white/70">
              {funnel.pendingPipelineValue.toLocaleString('tr-TR')} TRY
            </span>
            {funnel.pendingMissingPrice > 0 && ` (+${funnel.pendingMissingPrice} fiyatsız)`}
          </span>
        )}
      </div>
    </Card>
  )
}
