import { cn } from './ui'

/*
  Tailglass markasi. Isaret: siyah karo icinde turkuaz bir mercek (glass)
  ve ona akan beyaz bir iz (tail) — veriye bakan buyutec. Renkler sabit:
  siyah / turkuaz / beyaz; temadan bagimsiz, her zeminde ayni gorunur.
*/
export const TG = { black: '#0b0f0e', teal: '#1fc8b6', white: '#ffffff' }
export const PRODUCT = 'Tailglass Analytics'

export function TailglassMark({ size = 28, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" className={className} role="img" aria-label="Tailglass">
      <rect x=".5" y=".5" width="39" height="39" rx="9.5" fill={TG.black} stroke="rgba(255,255,255,.16)" />
      <path d="M6.5 33.5C11.5 32.4 14.6 29.6 17.6 25.2" stroke={TG.white} strokeWidth="3.2" strokeLinecap="round" fill="none" />
      <path d="M6.5 26.8C9.6 26.3 12.2 25 14.6 22.8" stroke={TG.teal} strokeWidth="2" strokeLinecap="round" fill="none" opacity=".75" />
      <circle cx="24.5" cy="16" r="8.2" stroke={TG.teal} strokeWidth="3.6" fill="none" />
      <path d="M20.6 13.6a4.6 4.6 0 0 1 3.4-2.5" stroke={TG.white} strokeWidth="1.8" strokeLinecap="round" fill="none" />
    </svg>
  )
}

/** Isaret + "tailglass Analytics" yazisi. Yazi rengi temaya uyar (siyah / beyaz). */
export function TailglassLogo({ size = 28, compact, className }: { size?: number; compact?: boolean; className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)} title={PRODUCT}>
      <TailglassMark size={size} />
      {!compact && (
        <span className="display leading-none whitespace-nowrap" style={{ fontSize: size * 0.62 }}>
          <span className="font-bold tracking-[-0.02em] text-ink">tailglass</span>
          <span className="ml-1 font-medium text-brand-ink">Analytics</span>
        </span>
      )}
    </span>
  )
}

/** Lisans sahibi sirketin logosu (Ayarlar'dan yuklenir); yoksa adi yazilir. */
export function CompanyBadge({ name, logo, logoDark, className }: { name?: string | null; logo?: string | null; logoDark?: string | null; className?: string }) {
  if (!logo && !name) return null
  return (
    <span className={cn('inline-flex min-w-0 items-center', className)}>
      {logo
        ? <>
            <img src={logo} alt={name || ''} className={cn('h-7 w-auto max-w-[170px] object-contain', logoDark && 'dark:hidden')} />
            {logoDark && <img src={logoDark} alt={name || ''} className="hidden h-7 w-auto max-w-[170px] object-contain dark:block" />}
          </>
        : <span className="truncate text-[15px] font-semibold text-ink">{name}</span>}
    </span>
  )
}
