import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { setSaleDuration } from '@/lib/api'

interface SetDurationModalProps {
  saleId: number
  clientName: string
  productName: string
  onClose: () => void
  onSaved: () => void
}

const PRESETS = [
  { label: '1 Yıl', months: 12 },
  { label: '2 Yıl', months: 24 },
  { label: '3 Yıl', months: 36 },
  { label: '5 Yıl', months: 60 },
]

type SendStatus = 'idle' | 'saving' | 'error'

export function SetDurationModal({ saleId, clientName, productName, onClose, onSaved }: SetDurationModalProps) {
  const [months, setMonths] = useState('')
  const [status, setStatus] = useState<SendStatus>('idle')
  const [message, setMessage] = useState('')

  async function handleSave(value: number) {
    if (!value || value <= 0) return
    setStatus('saving')
    const result = await setSaleDuration(saleId, value)
    if (result.success) {
      onSaved()
      onClose()
    } else {
      setMessage(result.message)
      setStatus('error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="w-full max-w-sm p-6">
        <h2 className="mb-1 text-lg font-semibold text-black/90 dark:text-white">Süre Girin</h2>
        <p className="mb-4 text-sm text-black/50 dark:text-white/50">
          {clientName} — {productName}
        </p>

        <div className="mb-4 grid grid-cols-4 gap-2">
          {PRESETS.map((p) => (
            <Button
              key={p.months}
              variant="ghost"
              className="px-2 text-xs"
              disabled={status === 'saving'}
              onClick={() => handleSave(p.months)}
            >
              {p.label}
            </Button>
          ))}
        </div>

        <div className="flex gap-3">
          <Input
            type="number"
            min={1}
            placeholder="Özel (ay)"
            value={months}
            onChange={(e) => setMonths(e.target.value)}
            className="flex-1"
          />
          <Button disabled={status === 'saving' || !months} onClick={() => handleSave(parseInt(months, 10))}>
            Kaydet
          </Button>
        </div>

        {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}

        <Button variant="ghost" className="mt-4 w-full" onClick={onClose} disabled={status === 'saving'}>
          Vazgeç
        </Button>
      </Card>
    </div>
  )
}
