import { Button } from '@/components/ui/button'
import { AnimatedBackground } from '@/components/AnimatedBackground'

interface SettingsPageProps {
  onBack: () => void
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-10">
      <AnimatedBackground />
      <div className="relative mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-display text-3xl italic text-white">Ayarlar</h1>
          <Button variant="ghost" className="text-white/70 hover:text-white hover:bg-white/10" onClick={onBack}>
            Geri
          </Button>
        </div>
        <p className="text-sm text-white/50">Yükleniyor...</p>
      </div>
    </div>
  )
}
