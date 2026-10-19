import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Button, inputCls } from '../components/ui'
import { CompanyBadge, TailglassLogo } from '../components/Brand'

export function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [marka, setMarka] = useState<{ company_name?: string; company_logo?: string; company_logo_dark?: string }>({})
  useEffect(() => { api.get<typeof marka>('/api/brand').then(setMarka, () => {}) }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/login', { username, password })
      onLogin()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Giriş yapılamadı.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-full place-items-center px-4 py-10">
      <div className="ledger-in w-full max-w-[400px]">
        <div className="mb-7 flex items-center justify-between gap-4">
          <TailglassLogo size={36} />
          <CompanyBadge name={marka.company_name} logo={marka.company_logo} logoDark={marka.company_logo_dark} className="opacity-90" />
        </div>
        <form onSubmit={submit} className="panel p-7">
          <h1 className="display text-[28px] leading-tight font-semibold">Hesabınıza girin</h1>
          <p className="mt-1.5 text-[13.5px] text-ink-2">Satış, stok ve lisans verilerine bu hesapla ulaşılır.</p>
          <div className="mt-6 flex flex-col gap-3.5">
            <label className="flex flex-col gap-1.5">
              <span className="text-[13px] font-medium">Kullanıcı adı</span>
              <input autoFocus autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} className={inputCls} />
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="text-[13px] font-medium">Şifre</span>
              <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} />
            </label>
          </div>
          {error && <p role="alert" className="mt-3.5 text-[13px] text-neg">{error}</p>}
          <Button type="submit" variant="primary" loading={busy} className="mt-6 w-full" disabled={!username || !password}>
            Giriş yap
          </Button>
        </form>
      </div>
    </div>
  )
}
