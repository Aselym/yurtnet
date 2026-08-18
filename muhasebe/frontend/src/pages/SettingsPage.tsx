import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { AnimatedBackground } from '@/components/AnimatedBackground'
import { SmtpSettingsCard } from '@/components/settings/SmtpSettingsCard'
import { LogoSettingsCard } from '@/components/settings/LogoSettingsCard'
import { AccountSettingsCard } from '@/components/settings/AccountSettingsCard'
import { SyncScheduleCard } from '@/components/settings/SyncScheduleCard'
import { getSettings } from '@/lib/api'

interface SettingsPageProps {
  onBack: () => void
}

type Status = 'loading' | 'error' | 'ready'

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<Status>('loading')

  async function load() {
    setStatus('loading')
    const data = await getSettings()
    if (data) {
      setSettings(data)
      setStatus('ready')
    } else {
      setStatus('error')
    }
  }

  useEffect(() => {
    load()
  }, [])

  function onChanged(patch: Record<string, string>) {
    setSettings((prev) => ({ ...prev, ...patch }))
  }

  return (
    <div className="relative min-h-screen overflow-hidden px-4 py-10">
      <AnimatedBackground />
      <div className="relative mx-auto max-w-2xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="font-display text-3xl italic text-white">Ayarlar</h1>
          <Button variant="ghost" className="text-white/70 hover:text-white hover:bg-white/10" onClick={onBack}>
            Geri
          </Button>
        </div>

        {status === 'loading' && <p className="text-sm text-white/50">Yükleniyor...</p>}

        {status === 'error' && (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-white/10 p-10 text-center">
            <p className="text-sm text-white/50">Ayarlar yüklenemedi.</p>
            <Button variant="ghost" className="text-white/70 hover:text-white hover:bg-white/10" onClick={load}>
              Tekrar dene
            </Button>
          </div>
        )}

        {status === 'ready' && (
          <>
            <SmtpSettingsCard settings={settings} onChanged={onChanged} />
            <LogoSettingsCard settings={settings} onChanged={onChanged} />
            <AccountSettingsCard settings={settings} />
            <SyncScheduleCard settings={settings} onChanged={onChanged} />
          </>
        )}
      </div>
    </div>
  )
}
