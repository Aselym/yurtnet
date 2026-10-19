import { useEffect, useRef, useState } from 'react'
import { AlertCircle, BellRing, Eye, EyeOff, FileSpreadsheet, Loader2, LockKeyhole, ShieldCheck, UserRound } from 'lucide-react'
import { api } from '../lib/api'
import { cn } from '../components/ui'
import { CompanyBadge, TailglassLogo } from '../components/Brand'

type Marka = { company_name?: string; company_logo?: string; company_logo_dark?: string }

/*
  Giris: kurumsal SaaS kalibi — solda marka paneli (siyah, yalnizca genis
  ekranda), sagda tek odakli form. Hata, Caps Lock ve deneme siniri acikca
  soylenir; "sifremi unuttum" bu uygulamada yonetici isidir, oyle yazar.
*/
export function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [show, setShow] = useState(false)
  const [caps, setCaps] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [forgot, setForgot] = useState(false)
  const [marka, setMarka] = useState<Marka>({})
  const sifreRef = useRef<HTMLInputElement>(null)

  useEffect(() => { api.get<Marka>('/api/brand').then(setMarka, () => {}) }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim() || !password) {
      setError('Kullanıcı adı ve şifre gerekli.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.post('/api/login', { username: username.trim(), password, remember })
      onLogin()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Giriş yapılamadı.')
      setPassword('')
      sifreRef.current?.focus()
    } finally {
      setBusy(false)
    }
  }

  const capsKontrol = (e: React.KeyboardEvent) => setCaps(e.getModifierState?.('CapsLock') ?? false)
  const sirket = marka.company_name

  return (
    <div className="grid min-h-full bg-canvas lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      {/* ---------------------------------------------------------- marka paneli */}
      <aside className="relative hidden overflow-hidden border-r border-white/10 bg-[#0b0f0e] text-white lg:flex lg:flex-col lg:justify-between lg:p-12 xl:p-14">
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[.07]"
          style={{ backgroundImage: 'linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)', backgroundSize: '44px 44px' }} />
        {/* isaretin turkuaz cam duzlemi, buyutulmus; metnin altinda kalir */}
        <svg aria-hidden viewBox="0 0 48 48" className="pointer-events-none absolute -right-[16%] -bottom-[38%] h-[82%] w-auto opacity-90">
          <path d="M16.18 19.5H26.18L18.98 42H8.98Z" fill="rgba(31,200,182,.10)" stroke="#1fc8b6" strokeOpacity=".55" strokeWidth=".18" />
        </svg>

        <TailglassLogo size={34} onDark className="relative" />

        <div className="relative max-w-[460px]">
          <h2 className="wordmark text-[40px] leading-[1.08] font-[600] tracking-[-0.03em] xl:text-[46px]">
            Logo’daki her satır,<br />tek bir ekranda.
          </h2>
          <p className="mt-5 text-[15.5px] leading-relaxed text-white/65">
            Satış, stok, kâr ve lisans yenilemeleri; şirketinizin kendi sunucusunda, Logo'ya yalnızca okuma erişimiyle.
          </p>
          <ul className="mt-9 flex flex-col gap-4 text-[14px] text-white/80">
            {[
              [ShieldCheck, 'Logo verisi değiştirilmez, yalnızca okunur'],
              [BellRing, 'Süresi dolan lisanslar için zamanında hatırlatma'],
              [FileSpreadsheet, 'Her tablo ve rapor tek tıkla Excel’de'],
            ].map(([Ikon, metin]) => {
              const I = Ikon as typeof ShieldCheck
              return (
                <li key={metin as string} className="flex items-center gap-3">
                  <span className="grid size-8 place-items-center rounded-[var(--radius-panel)] border border-white/12 bg-white/[.04]"><I className="size-4 text-[#1fc8b6]" /></span>
                  {metin as string}
                </li>
              )
            })}
          </ul>
        </div>

        <p className="relative text-[12.5px] text-white/40">© {new Date().getFullYear()} Tailglass Analytics</p>
      </aside>

      {/* ---------------------------------------------------------- form */}
      <main className="flex flex-col px-6 py-8 sm:px-10">
        <div className="flex items-center justify-between lg:justify-end">
          <TailglassLogo size={28} className="lg:hidden" />
          <CompanyBadge name={sirket} logo={marka.company_logo} logoDark={marka.company_logo_dark} className="opacity-90" />
        </div>

        <div className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center py-12">
          <div className="ledger-in">
            <h1 className="wordmark text-[30px] leading-tight font-[600] tracking-[-0.025em] text-ink">Oturum açın</h1>
            <p className="mt-2 text-[14.5px] text-ink-2">
              {sirket ? <>{sirket} çalışma alanına devam etmek için hesap bilgilerinizi girin.</> : 'Devam etmek için hesap bilgilerinizi girin.'}
            </p>

            <form onSubmit={submit} noValidate className="mt-8 flex flex-col gap-5">
              {error && (
                <div role="alert" className="flex items-start gap-2.5 rounded-[var(--radius-panel)] border border-neg/30 bg-neg/[.06] px-3.5 py-3 text-[13.5px] text-neg">
                  <AlertCircle className="mt-px size-4 shrink-0" /> <span>{error}</span>
                </div>
              )}

              <Alan etiket="Kullanıcı adı" ikon={UserRound}>
                <input id="kullanici" autoFocus autoComplete="username" spellCheck={false} value={username}
                  onChange={(e) => setUsername(e.target.value)} className={girdi} placeholder="ör. admin" />
              </Alan>

              <Alan etiket="Şifre" ikon={LockKeyhole} sag={
                <button type="button" onClick={() => setShow(!show)} aria-label={show ? 'Şifreyi gizle' : 'Şifreyi göster'}
                  className="grid size-9 place-items-center rounded-[var(--radius-ctl)] text-muted hover:text-ink">
                  {show ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
                </button>
              }>
                <input id="sifre" ref={sifreRef} type={show ? 'text' : 'password'} autoComplete="current-password" value={password}
                  onChange={(e) => setPassword(e.target.value)} onKeyUp={capsKontrol} onKeyDown={capsKontrol}
                  className={cn(girdi, 'pr-11')} placeholder="••••••••" />
              </Alan>
              {caps && <p className="-mt-3 text-[12.5px] text-[var(--warning)]">Caps Lock açık.</p>}

              <div className="flex items-center justify-between text-[13.5px]">
                <label className="flex cursor-pointer items-center gap-2 text-ink-2 select-none">
                  <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="size-4 accent-[var(--brand)]" />
                  Beni hatırla
                </label>
                <button type="button" onClick={() => setForgot(!forgot)} className="font-medium text-brand-ink hover:underline" aria-expanded={forgot}>
                  Şifremi unuttum
                </button>
              </div>
              {forgot && (
                <p className="-mt-2 rounded-[var(--radius-panel)] bg-surface-2 px-3.5 py-3 text-[13px] leading-relaxed text-ink-2">
                  Şifreler sistem yöneticisi tarafından <b className="font-semibold text-ink">Ayarlar &gt; Hesap</b> bölümünden yenilenir.
                  Erişiminiz yoksa şirketinizin BT sorumlusuna başvurun.
                </p>
              )}

              <button type="submit" disabled={busy}
                className="mt-1 inline-flex h-11 items-center justify-center gap-2 rounded-[var(--radius-panel)] bg-[#0b0f0e] text-[14.5px] font-semibold text-white transition hover:bg-[#1a2321] disabled:opacity-70 dark:bg-brand dark:text-on-brand dark:hover:brightness-105">
                {busy && <Loader2 className="size-4 animate-spin" />}
                {busy ? 'Giriş yapılıyor' : 'Giriş yap'}
              </button>
            </form>
          </div>
        </div>

        <p className="text-center text-[12px] text-muted">
          Tailglass Analytics{sirket ? ` — ${sirket} için lisanslıdır` : ''}
        </p>
      </main>
    </div>
  )
}

const girdi = 'h-11 w-full rounded-[var(--radius-panel)] border border-line-strong bg-surface pr-3 pl-10 text-[14.5px] text-ink outline-none transition placeholder:text-muted/70 focus:border-ink focus:ring-4 focus:ring-[color-mix(in_oklab,var(--brand)_28%,transparent)]'

function Alan({ etiket, ikon: Ikon, sag, children }: { etiket: string; ikon: typeof UserRound; sag?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-ink">{etiket}</span>
      <span className="relative block">
        <Ikon className="pointer-events-none absolute top-1/2 left-3.5 size-[18px] -translate-y-1/2 text-muted" />
        {children}
        {sag && <span className="absolute top-1/2 right-1 -translate-y-1/2">{sag}</span>}
      </span>
    </label>
  )
}
