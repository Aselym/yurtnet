import { Button } from '@/components/ui/button'
import type { Role } from '@/lib/types'

interface PlaceholderPanelProps {
  role: Role
  onLogout: () => void
}

const roleLabels: Record<Role, string> = {
  yonetici: 'Yönetici Paneli',
  satis: 'Satış ve Muhasebe Paneli',
}

export function PlaceholderPanel({ role, onLogout }: PlaceholderPanelProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-bg px-4 text-center dark:bg-neutral-950">
      <h1 className="text-2xl font-semibold text-black/80 dark:text-white/90">{roleLabels[role]}</h1>
      <p className="max-w-md text-sm text-black/50 dark:text-white/50">
        Bu ekran Faz 2/3'te gerçek içerikle değiştirilecek. Giriş ve rol seçimi akışı burada test edilebilir.
      </p>
      <Button variant="ghost" onClick={onLogout} className="mt-4">
        Çıkış Yap
      </Button>
    </div>
  )
}
