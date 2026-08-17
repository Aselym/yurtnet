import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { createOffer, type NewOffer } from '@/lib/api'

interface NewOfferModalProps {
  onClose: () => void
  onCreated: () => void
  initial?: { client_name: string; product_name: string; notes?: string }
}

type SendStatus = 'idle' | 'saving' | 'error'

const today = () => new Date().toISOString().slice(0, 10)

export function NewOfferModal({ onClose, onCreated, initial }: NewOfferModalProps) {
  const [form, setForm] = useState({
    product_name: initial?.product_name ?? '',
    quantity: '1',
    client_name: initial?.client_name ?? '',
    offer_price: '',
    currency: 'TRY',
    offer_date: today(),
    sales_rep: '',
    notes: initial?.notes ?? '',
  })
  const [status, setStatus] = useState<SendStatus>('idle')
  const [message, setMessage] = useState('')

  const canSubmit = form.product_name.trim() !== '' && form.client_name.trim() !== ''

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSubmit() {
    if (!canSubmit) return
    setStatus('saving')
    const payload: NewOffer = {
      product_name: form.product_name.trim(),
      quantity: parseInt(form.quantity, 10) || 1,
      client_name: form.client_name.trim(),
      offer_price: parseFloat(form.offer_price) || 0,
      currency: form.currency,
      offer_date: form.offer_date,
      sales_rep: form.sales_rep.trim(),
      notes: form.notes.trim(),
    }
    const result = await createOffer(payload)
    if (result.success) {
      onCreated()
      onClose()
    } else {
      setMessage(result.message)
      setStatus('error')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <Card className="w-full max-w-md p-6">
        <h2 className="mb-4 text-lg font-semibold text-black/90 dark:text-white">Yeni Teklif</h2>

        <div className="space-y-3">
          <Input
            placeholder="Müşteri"
            value={form.client_name}
            onChange={(e) => update('client_name', e.target.value)}
          />
          <Input
            placeholder="Ürün"
            value={form.product_name}
            onChange={(e) => update('product_name', e.target.value)}
          />
          <div className="flex gap-3">
            <Input
              type="number"
              min={1}
              placeholder="Adet"
              value={form.quantity}
              onChange={(e) => update('quantity', e.target.value)}
              className="w-24"
            />
            <Input
              type="number"
              min={0}
              placeholder="Fiyat"
              value={form.offer_price}
              onChange={(e) => update('offer_price', e.target.value)}
              className="flex-1"
            />
            <Input
              placeholder="Para Birimi"
              value={form.currency}
              onChange={(e) => update('currency', e.target.value)}
              className="w-20"
            />
          </div>
          <div className="flex gap-3">
            <Input
              type="date"
              value={form.offer_date}
              onChange={(e) => update('offer_date', e.target.value)}
              className="flex-1"
            />
            <Input
              placeholder="Satış Temsilcisi"
              value={form.sales_rep}
              onChange={(e) => update('sales_rep', e.target.value)}
              className="flex-1"
            />
          </div>
          <Input
            placeholder="Not (opsiyonel)"
            value={form.notes}
            onChange={(e) => update('notes', e.target.value)}
          />
        </div>

        {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}

        <div className="mt-5 flex gap-3">
          <Button variant="ghost" className="flex-1" onClick={onClose} disabled={status === 'saving'}>
            Vazgeç
          </Button>
          <Button className="flex-1" onClick={handleSubmit} disabled={!canSubmit || status === 'saving'}>
            {status === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
