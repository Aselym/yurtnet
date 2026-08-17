import { Card } from '@/components/ui/card'
import {
  getMonthlyExpiryBuckets,
  getStatusCounts,
  type MonthlyExpiryBucket,
  type StatusCount,
} from '@/lib/licenseAnalytics'
import type { Sale } from '@/lib/api'

const GRID = '#e1e0d9'
const GRID_DARK = '#2c2c2a'

interface StatusBarChartProps {
  sales: Sale[]
}

export function StatusBarChart({ sales }: StatusBarChartProps) {
  const data = getStatusCounts(sales)
  const max = Math.max(1, ...data.map((d) => d.count))
  const rowHeight = 32
  const barMaxWidth = 260
  const height = data.length * rowHeight + 12

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">Lisans Durumu Dağılımı</h3>
      <svg viewBox={`0 0 420 ${height}`} width="100%" height={height} role="img" aria-label="Lisans durumu dağılımı">
        {data.map((d: StatusCount, i) => {
          const y = i * rowHeight + 6
          const w = (d.count / max) * barMaxWidth
          return (
            <g key={d.status}>
              <text
                x={0}
                y={y + 14}
                className="fill-current text-black/60 dark:text-white/60"
                fontSize={12}
              >
                {d.label}
              </text>
              <rect x={140} y={y + 4} width={barMaxWidth} height={16} rx={4} className="fill-current text-black/[0.03] dark:text-white/[0.05]" />
              {d.count > 0 && (
                <rect x={140} y={y + 4} width={Math.max(w, 4)} height={16} rx={4} fill={d.color}>
                  <title>{`${d.label}: ${d.count}`}</title>
                </rect>
              )}
              <text
                x={140 + barMaxWidth + 10}
                y={y + 16}
                className="fill-current text-black/70 dark:text-white/70"
                fontSize={12}
                fontWeight={600}
              >
                {d.count}
              </text>
            </g>
          )
        })}
      </svg>
    </Card>
  )
}

interface MonthlyExpiryChartProps {
  sales: Sale[]
}

export function MonthlyExpiryChart({ sales }: MonthlyExpiryChartProps) {
  const data = getMonthlyExpiryBuckets(sales, 6)
  const max = Math.max(1, ...data.map((d) => d.count))
  const width = 420
  const height = 200
  const plotHeight = 140
  const plotBottom = 160
  const colWidth = width / data.length
  const barWidth = 28

  return (
    <Card className="p-5">
      <h3 className="mb-4 text-sm font-semibold text-black/70 dark:text-white/70">
        Önümüzdeki 6 Ay — Süresi Dolacak Lisanslar
      </h3>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} role="img" aria-label="Önümüzdeki 6 ay süresi dolacak lisans sayısı">
        <line
          x1={0}
          y1={plotBottom}
          x2={width}
          y2={plotBottom}
          stroke={GRID}
          strokeWidth={1}
          className="dark:hidden"
        />
        <line
          x1={0}
          y1={plotBottom}
          x2={width}
          y2={plotBottom}
          stroke={GRID_DARK}
          strokeWidth={1}
          className="hidden dark:block"
        />
        {data.map((d: MonthlyExpiryBucket, i) => {
          const barHeight = (d.count / max) * plotHeight
          const cx = i * colWidth + colWidth / 2
          const x = cx - barWidth / 2
          const y = plotBottom - barHeight
          return (
            <g key={d.key}>
              {d.count > 0 && (
                <rect x={x} y={y} width={barWidth} height={Math.max(barHeight, 2)} rx={4} className="fill-brand">
                  <title>{`${d.label}: ${d.count} lisans`}</title>
                </rect>
              )}
              {d.count > 0 && (
                <text
                  x={cx}
                  y={y - 6}
                  textAnchor="middle"
                  className="fill-current text-black/70 dark:text-white/70"
                  fontSize={12}
                  fontWeight={600}
                >
                  {d.count}
                </text>
              )}
              <text
                x={cx}
                y={plotBottom + 18}
                textAnchor="middle"
                className="fill-current text-black/40 dark:text-white/40"
                fontSize={11}
              >
                {d.label}
              </text>
            </g>
          )
        })}
      </svg>
    </Card>
  )
}
