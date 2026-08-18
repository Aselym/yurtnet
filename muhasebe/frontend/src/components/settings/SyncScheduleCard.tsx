import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { updateSettings } from '@/lib/api'

interface SyncScheduleCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type Status = 'idle' | 'saving' | 'error'

export function SyncScheduleCard({ settings, onChanged }: SyncScheduleCardProps) {
  const [enabled, setEnabled] = useState((settings.logo_auto_sync ?? 'OFF') === 'ON')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')

  async function handleToggle(next: boolean) {
    setEnabled(next)
    setStatus('saving')
    const value = next ? 'ON' : 'OFF'
    const result = await updateSettings({ logo_auto_sync: value })
    if (result.success) {
      onChanged({ logo_auto_sync: value })
      setStatus('idle')
    } else {
      setEnabled(!next)
      setMessage(result.message)
      setStatus('error')
    }
  }

  return (
    <Card className="p-6">
      <h2 className="mb-1 text-sm font-semibold text-black/80 dark:text-white/90">Otomatik Senkronizasyon</h2>
      <p className="mb-4 text-xs text-black/40 dark:text-white/40">
        Açıkken Logo'dan lisans/abonelik/ürün verisi günde 3 kez (11:00, 15:00, 17:00) otomatik çekilir.
      </p>

      <label className="flex items-center gap-3">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => handleToggle(e.target.checked)}
          disabled={status === 'saving'}
        />
        <span className="text-sm text-black/80 dark:text-white/80">
          {enabled ? 'Açık' : 'Kapalı'}
        </span>
      </label>

      {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}
    </Card>
  )
}
