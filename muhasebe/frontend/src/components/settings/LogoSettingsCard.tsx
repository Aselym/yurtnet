import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { testLogoConnection, triggerLogoSync, updateSettings } from '@/lib/api'

interface LogoSettingsCardProps {
  settings: Record<string, string>
  onChanged: (patch: Record<string, string>) => void
}

type SaveStatus = 'idle' | 'saving' | 'error' | 'success'
type ActionStatus = 'idle' | 'running' | 'error' | 'success'

export function LogoSettingsCard({ settings, onChanged }: LogoSettingsCardProps) {
  const [form, setForm] = useState({
    logo_sql_server: settings.logo_sql_server ?? '',
    logo_sql_port: settings.logo_sql_port ?? '',
    logo_sql_db: settings.logo_sql_db ?? '',
    logo_sql_user: settings.logo_sql_user ?? '',
    logo_sql_pass: settings.logo_sql_pass ?? '',
    logo_firm_no: settings.logo_firm_no ?? '',
    logo_period_no: settings.logo_period_no ?? '',
  })
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle')
  const [saveMessage, setSaveMessage] = useState('')
  const [testStatus, setTestStatus] = useState<ActionStatus>('idle')
  const [testMessage, setTestMessage] = useState('')
  const [syncStatus, setSyncStatus] = useState<ActionStatus>('idle')
  const [syncMessage, setSyncMessage] = useState('')

  function update<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function handleSave() {
    setSaveStatus('saving')
    const result = await updateSettings(form)
    if (result.success) {
      onChanged(form)
      setSaveStatus('success')
    } else {
      setSaveStatus('error')
    }
    setSaveMessage(result.message)
  }

  async function handleTest() {
    setTestStatus('running')
    const saveResult = await updateSettings(form)
    if (!saveResult.success) {
      setTestMessage(saveResult.message)
      setTestStatus('error')
      return
    }
    onChanged(form)
    const result = await testLogoConnection()
    setTestMessage(result.message)
    setTestStatus(result.success ? 'success' : 'error')
  }

  async function handleSync() {
    setSyncStatus('running')
    const saveResult = await updateSettings(form)
    if (!saveResult.success) {
      setSyncMessage(saveResult.message)
      setSyncStatus('error')
      return
    }
    onChanged(form)
    const result = await triggerLogoSync()
    setSyncMessage(result.message)
    setSyncStatus(result.success ? 'success' : 'error')
  }

  return (
    <Card className="p-6">
      <h2 className="mb-4 text-sm font-semibold text-black/80 dark:text-white/90">Logo Bağlantı Ayarları</h2>
      <div className="space-y-3">
        <div className="flex gap-3">
          <Input
            placeholder="SQL Sunucu"
            value={form.logo_sql_server}
            onChange={(e) => update('logo_sql_server', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Port"
            value={form.logo_sql_port}
            onChange={(e) => update('logo_sql_port', e.target.value)}
            className="w-24"
          />
        </div>
        <Input
          placeholder="Veritabanı Adı"
          value={form.logo_sql_db}
          onChange={(e) => update('logo_sql_db', e.target.value)}
        />
        <Input
          placeholder="SQL Kullanıcı Adı"
          value={form.logo_sql_user}
          onChange={(e) => update('logo_sql_user', e.target.value)}
        />
        <Input
          type="password"
          placeholder="SQL Şifre"
          value={form.logo_sql_pass}
          onChange={(e) => update('logo_sql_pass', e.target.value)}
          autoComplete="new-password"
        />
        <div className="flex gap-3">
          <Input
            placeholder="Firma No"
            value={form.logo_firm_no}
            onChange={(e) => update('logo_firm_no', e.target.value)}
            className="flex-1"
          />
          <Input
            placeholder="Dönem No"
            value={form.logo_period_no}
            onChange={(e) => update('logo_period_no', e.target.value)}
            className="flex-1"
          />
        </div>
      </div>

      {saveStatus !== 'idle' && saveStatus !== 'saving' && (
        <p className={`mt-3 text-sm ${saveStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {saveMessage}
        </p>
      )}
      {testStatus !== 'idle' && testStatus !== 'running' && (
        <p className={`mt-3 text-sm ${testStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {testMessage}
        </p>
      )}
      {syncStatus !== 'idle' && syncStatus !== 'running' && (
        <p className={`mt-3 text-sm ${syncStatus === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {syncMessage}
        </p>
      )}

      <div className="mt-5 flex flex-wrap gap-3">
        <Button variant="ghost" className="flex-1" onClick={handleTest} disabled={testStatus === 'running'}>
          {testStatus === 'running' ? 'Test ediliyor...' : 'Bağlantıyı Test Et'}
        </Button>
        <Button variant="ghost" className="flex-1" onClick={handleSync} disabled={syncStatus === 'running'}>
          {syncStatus === 'running' ? 'Senkronize ediliyor...' : 'Şimdi Senkronize Et'}
        </Button>
        <Button className="flex-1" onClick={handleSave} disabled={saveStatus === 'saving'}>
          {saveStatus === 'saving' ? 'Kaydediliyor...' : 'Kaydet'}
        </Button>
      </div>
    </Card>
  )
}
