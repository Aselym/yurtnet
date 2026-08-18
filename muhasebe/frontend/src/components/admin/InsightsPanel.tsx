import { AlertOctagon, AlertTriangle, CheckCircle2, type LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { generateInsights, type Insight, type InsightSeverity } from '@/lib/adminAnalytics'
import type { Offer, Sale, Subscription } from '@/lib/api'

interface SeverityStyle {
  icon: LucideIcon
  className: string
  label: string
}

// StatCard.tsx'in warn/danger tonlarıyla aynı Tailwind sınıfları — renk tek
// başına anlam taşımasın diye her zaman ikon + etiketle birlikte kullanılır.
const SEVERITY_STYLES: Record<InsightSeverity, SeverityStyle> = {
  good: { icon: CheckCircle2, className: 'text-green-700 bg-green-50 dark:text-green-400 dark:bg-green-500/10', label: 'İyi' },
  warning: {
    icon: AlertTriangle,
    className: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10',
    label: 'Dikkat',
  },
  critical: { icon: AlertOctagon, className: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10', label: 'Kritik' },
}

interface InsightsPanelProps {
  sales: Sale[]
  subscriptions: Subscription[]
  offers: Offer[]
}

export function InsightsPanel({ sales, subscriptions, offers }: InsightsPanelProps) {
  const insights = generateInsights(sales, subscriptions, offers)

  return (
    <Card className="p-5">
      <h3 className="mb-1 text-sm font-semibold text-black/70 dark:text-white/70">Otomatik Tavsiyeler</h3>
      <p className="mb-4 text-xs text-black/40 dark:text-white/40">
        Mevcut veriden kural tabanlı olarak üretilir — yapay zeka tahmini değildir.
      </p>
      <div className="space-y-2">
        {insights.map((insight, i) => (
          <InsightRow key={i} insight={insight} />
        ))}
      </div>
    </Card>
  )
}

function InsightRow({ insight }: { insight: Insight }) {
  const { icon: Icon, className, label } = SEVERITY_STYLES[insight.severity]
  return (
    <div className="flex items-start gap-3 rounded-xl bg-black/[0.02] p-3 dark:bg-white/[0.03]">
      <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${className}`}>
        <Icon className="h-4 w-4" strokeWidth={1.75} />
      </span>
      <div>
        <p className="text-[11px] font-medium uppercase tracking-wide text-black/40 dark:text-white/40">{label}</p>
        <p className="text-sm text-black/80 dark:text-white/80">{insight.text}</p>
      </div>
    </div>
  )
}
