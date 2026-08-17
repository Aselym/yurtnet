import { cn } from '@/lib/cn'

const STATUS_STYLES: Record<string, string> = {
  PENDING: 'bg-blue-50 text-blue-600 dark:bg-blue-500/10 dark:text-blue-400',
  FIRST_REMINDER_SENT: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  FINAL_REMINDER_SENT: 'bg-orange-50 text-orange-600 dark:bg-orange-500/10 dark:text-orange-400',
  EXPIRED: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
  NEEDS_DURATION: 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-white/60',
  RENEWED: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  ACTIVE: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  AT_RISK: 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400',
  LOST: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
  ACCEPTED: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10 dark:text-emerald-400',
  REJECTED: 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400',
}

const STATUS_LABELS: Record<string, string> = {
  PENDING: 'Beklemede',
  FIRST_REMINDER_SENT: 'İlk Hatırlatma Gönderildi',
  FINAL_REMINDER_SENT: 'Son Hatırlatma Gönderildi',
  EXPIRED: 'Süresi Doldu',
  NEEDS_DURATION: 'Süre Girilmeli',
  RENEWED: 'Yenilendi',
  ACTIVE: 'Aktif',
  AT_RISK: 'Riskli',
  LOST: 'Kayıp',
  ACCEPTED: 'Kabul Edildi',
  REJECTED: 'Reddedildi',
}

interface StatusPillProps {
  status: string
}

export function StatusPill({ status }: StatusPillProps) {
  const style = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600 dark:bg-white/10 dark:text-white/60'
  const label = STATUS_LABELS[status] ?? status

  return (
    <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', style)}>
      {label}
    </span>
  )
}
