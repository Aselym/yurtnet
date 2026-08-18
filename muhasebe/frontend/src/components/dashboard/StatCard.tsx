import type { LucideIcon } from 'lucide-react'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/cn'

interface StatCardProps {
  label: string
  value: number | string
  icon: LucideIcon
  tone?: 'default' | 'warn' | 'danger'
}

const TONE_STYLES: Record<NonNullable<StatCardProps['tone']>, string> = {
  default: 'text-brand-dark bg-brand-soft dark:text-brand dark:bg-brand/10',
  warn: 'text-amber-600 bg-amber-50 dark:text-amber-400 dark:bg-amber-500/10',
  danger: 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-500/10',
}

export function StatCard({ label, value, icon: Icon, tone = 'default' }: StatCardProps) {
  return (
    <Card className="flex items-center gap-4 p-5">
      <div className={cn('flex h-12 w-12 shrink-0 items-center justify-center rounded-xl', TONE_STYLES[tone])}>
        <Icon className="h-6 w-6" strokeWidth={1.75} />
      </div>
      <div>
        <p className="text-2xl font-semibold text-black/90 dark:text-white">{value}</p>
        <p className="text-sm text-black/50 dark:text-white/50">{label}</p>
      </div>
    </Card>
  )
}
