import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { InfoTip } from '@/components/ui/info-tip'
import { cn } from '@/lib/cn'

interface StatCardProps {
  label: string
  value: number | string
  icon: LucideIcon
  tone?: 'default' | 'warn' | 'danger'
  /** Deger kisaltilmis/yuvarlanmis oldugunda tam degeri gostermek icin (native tooltip). */
  title?: string
  /** Rakamin ne anlama geldigini ve nasil hesaplandigini acan ipucu — teknik olmayan yoneticiler icin sart. */
  info?: ReactNode
}

const TONE_STYLES: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'text-brand-dark bg-brand-soft dark:text-brand dark:bg-brand/10',
  warn: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10',
  danger: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10',
}

export function StatCard({ label, value, icon: Icon, tone = 'default', title, info }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4 p-5" title={title}>
      <div className={cn('flex h-12 w-12 shrink-0 items-center justify-center rounded-xl', TONE_STYLES[tone])}>
        <Icon className="h-6 w-6" strokeWidth={1.75} />
      </div>
      <div className="min-w-0">
        <p className="truncate text-2xl font-semibold text-black/90 dark:text-white">{value}</p>
        <p className="flex items-center gap-1 text-sm text-black/50 dark:text-white/50">
          <span className="truncate">{label}</span>
          {info && <InfoTip>{info}</InfoTip>}
        </p>
      </div>
    </Card>
  )
}
