import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { sendTestEmail, updateSettings } from '@/lib/api'

interface SmtpSettingsCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type SaveStatus = 'idle' | 'saving' | 'error' | 'success'
type TestStatus = 'idle' | 'sending' | 'error' | 'success'

export function SmtpSettingsCard({ settings, onChanged }: SmtpSettingsCardProps) {
  const [form, setForm] = useState({
    smtp_host: settings.smtp_host ?? '',
    smtp_port: settings.smtp_port ?? '',
    smtp_user: settings.smtp_user ?? '',
    smtp_password: settings.smtp_password ?? '',
    sender_email: settings.sender_email ?? '',
    sender_name: settings.sender_name ?? '',
    internal_recipients: settings.internal_recipients ?? '',
  })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [saveMessage, setSaveMessage] = useState('')
  const [testStatus, setTestStatus] = useState<TestStatus>('idle')
  const [testMessage, setTestMessage] = useState('')

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSave() {
    setSaveStatus('saving')
    const result = await updateSettings(form)
    if (result.success) {
      onChanged(form)
      setSaveStatus('success')
      setSaveMessage(result.message)
    } else {
      setSaveStatus('error')
      setSaveMessage(result.message)
    }
  }

  async function handleTest() {
    setTestStatus('sending')
    const saveResult = await updateSettings(form)
    if (!saveResult.success) {
      setTestMessage(saveResult.message)
      setTestStatus('error')
      return
    }
    onChanged(form)
    const result = await sendTestEmail(form.internal_recipients)
    setTestMessage(result.message)
    setTestStatus(result.success ? 'success' : 'error')
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">SMTP Ayarları</h2>
      <div className="space-y-3">
        <div className="flex gap-3">
          <Input
            placeholder="SMTP Sunucu"
            value={form.smtp_host}
            onChange={(e) => update('smtp_host', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Port"
            value={form.smtp_port}
            onChange={(e) => update('smtp_port', e.target.value)}
            className="w-24"
          />
        </div>
        <Input
          placeholder="SMTP Kullanıcı Adı"
          value={form.smtp_user}
          onChange={(e) => update('smtp_user', e.target.value)}
        />
        <Input
          type="password"
          placeholder="SMTP Şifre"
          value={form.smtp_password}
          onChange={(e) => update('smtp_password', e.target.value)}
          autoComplete="new-password"
        />
        <div className="flex gap-3">
          <Input
            placeholder="Gönderen E-posta"
            value={form.sender_email}
            onChange={(e) => update('sender_email', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Gönderen Adı"
            value={form.sender_name}
            onChange={(e) => update('sender_name', e.target.value)}
            className="flex-1"
          />
        </div>
        <Input
          placeholder="İç Bildirim Alıcıları (virgülle ayırın)"
          value={form.internal_recipients}
          onChange={(e) => update('internal_recipients', e.target.value)}
        />
      </div>

      {saveStatus === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{saveMessage}</p>}
      {saveStatus === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{saveMessage}</p>}
      {testStatus === 'error' && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{testMessage}</p>}
      {testStatus === 'success' && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{testMessage}</p>}

      <div className="mt-5 flex gap-3">
        <Button variant="ghost" className="flex-1" onClick={handleTest} disabled={testStatus === 'sending'}>
          {testStatus === 'sending' ? 'Gönderiliyor...' : 'Test E-postası Gönder'}
        </Button>
        <Button className="flex-1" onClick={handleSave} disabled={saveStatus === 'saving'}>
          {saveStatus === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
        </Button>
      </div>
    </Card>
  )
}
