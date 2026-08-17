import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { getSettings, sendReminder, type ReminderStage } from '@/lib/api'

interface ReminderModalProps {
  saleId: number
  clientName: string
  productName: string
  expirationDate: string
  daysLeft: number
  onClose: () => void
}

type RecipientsStatus = 'loading' | 'error' | 'ready'
type SendStatus = 'idle' | 'sending' | 'success' | 'error'

export function ReminderModal({
  saleId,
  clientName,
  productName,
  expirationDate,
  daysLeft,
  onClose,
}: ReminderModalProps) {
  const [recipientsStatus, setRecipientsStatus] = useState<RecipientsStatus>('loading')
  const [recipients, setRecipients] = useState<string[]>([])
  const [sendStatus, setSendStatus] = useState<SendStatus>('idle')
  const [sendMessage, setSendMessage] = useState('')

  useEffect(() => {
    let cancelled = false
    getSettings().then((settings) => {
      if (cancelled) return
      if (!settings) {
        setRecipientsStatus('error')
        return
      }
      const raw = settings.internal_recipients ?? ''
      const list = raw
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
      setRecipients(list)
      setRecipientsStatus('ready')
    })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSend() {
    setSendStatus('sending')
    const stage: ReminderStage = daysLeft <= 7 ? 'FINAL_REMINDER' : 'FIRST_REMINDER'
    const result = await sendReminder(saleId, stage)
    setSendMessage(result.message)
    setSendStatus(result.success ? 'success' : 'error')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="w-full max-w-md p-6">
        <h2 className="mb-1 text-lg font-semibold text-black/90 dark:text-white">Hatırlatma Gönder</h2>
        <p className="mb-4 text-sm text-black/50 dark:text-white/50">
          {clientName} — {productName} ({expirationDate},{' '}
          {daysLeft >= 0 ? `${daysLeft} gün kaldı` : 'süresi doldu'})
        </p>

        {sendStatus === 'success' ? (
          <div className="space-y-4">
            <p className="text-sm text-emerald-600 dark:text-emerald-400">{sendMessage}</p>
            <Button className="w-full" onClick={onClose}>
              Kapat
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {recipientsStatus === 'loading' && (
              <p className="text-sm text-black/50 dark:text-white/50">Alıcı listesi yükleniyor...</p>
            )}
            {recipientsStatus === 'error' && (
              <p className="text-sm text-red-600 dark:text-red-400">Alıcı listesi yüklenemedi.</p>
            )}
            {recipientsStatus === 'ready' &&
              (recipients.length > 0 ? (
                <p className="text-sm text-black/70 dark:text-white/70">
                  Bu bildirim şu adreslere gidecek: <strong>{recipients.join(', ')}</strong>. Emin misiniz?
                </p>
              ) : (
                <p className="text-sm text-red-600 dark:text-red-400">
                  Alıcı listesi boş. Ayarlar sekmesinden iç bildirim adreslerini ekleyin.
                </p>
              ))}

            {sendStatus === 'error' && <p className="text-sm text-red-600 dark:text-red-400">{sendMessage}</p>}

            <div className="flex gap-3">
              <Button
                variant="ghost"
                className="flex-1"
                onClick={onClose}
                disabled={sendStatus === 'sending'}
              >
                Vazgeç
              </Button>
              <Button
                className="flex-1"
                onClick={handleSend}
                disabled={sendStatus === 'sending' || recipientsStatus !== 'ready' || recipients.length === 0}
              >
                {sendStatus === 'sending' ? 'Gönderiliyor...' : 'Tamam, Gönder'}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
