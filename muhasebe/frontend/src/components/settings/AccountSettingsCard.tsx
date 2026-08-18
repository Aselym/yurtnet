import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { updateAccount } from '@/lib/api'

interface AccountSettingsCardProps {
  settings: Record<string, string>
}

type Status = 'idle' | 'saving' | 'error' | 'success'

export function AccountSettingsCard({ settings }: AccountSettingsCardProps) {
  const [newUsername, setNewUsername] = useState(settings.admin_user ?? '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState('')

  const canSubmit = currentPassword.trim() !== ''

  async function handleSave() {
    if (!canSubmit) return
    setStatus('saving')
    const result = await updateAccount({
      current_password: currentPassword,
      new_username: newUsername.trim() || undefined,
      new_password: newPassword.trim() || undefined,
    })
    setMessage(result.message)
    if (result.success) {
      setStatus('success')
      setCurrentPassword('')
      setNewPassword('')
    } else {
      setStatus('error')
    }
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">Hesap Bilgisi</h2>
      <div className="space-y-3">
        <Input
          placeholder="Kullanıcı Adı"
          value={newUsername}
          onChange={(e) => setNewUsername(e.target.value)}
        />
        <Input
          type="password"
          placeholder="Yeni Şifre (opsiyonel)"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          autoComplete="new-password"
        />
        <Input
          type="password"
          placeholder="Mevcut Şifre (onay için gerekli)"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          autoComplete="current-password"
        />
      </div>

      {status === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{message}</p>}
      {status === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}

      <Button className="mt-5 w-full" onClick={handleSave} disabled={!canSubmit || status === 'saving'}>
        {status === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
      </Button>
    </Card>
  )
}
