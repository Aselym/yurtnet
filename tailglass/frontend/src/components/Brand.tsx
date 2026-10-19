import { cn } from './ui'

/*
  Tailglass markasi — "Prizma T": ayni egimde iki cam duzlem.
  Ust cubuk murekkep rengi (acik temada siyah, koyuda beyaz), govde turkuaz.
  Egim 0.32 (dx/dy) iki parcada da ayni; govde, cubugun egik orta eksenine
  oturur. Yazi: Instrument Sans — "Tailglass" kalin, "Analytics" ince ve gri.
*/
export const TG = { black: '#0b0f0e', teal: '#1fc8b6', white: '#ffffff' }
export const PRODUCT = 'Tailglass Analytics'

const CUBUK = 'M7 6H44L40.8 16H3.8Z'
const GOVDE = 'M16.18 19.5H26.18L18.98 42H8.98Z'

export function TailglassMark({ size = 28, className, tile }: { size?: number; className?: string; tile?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" className={cn('shrink-0', className)} role="img" aria-label="Tailglass">
      {tile && <rect width="48" height="48" rx="7" fill={TG.black} />}
      <g transform={tile ? 'translate(4.8 4.8) scale(.8)' : undefined}>
        <path d={CUBUK} fill={tile ? TG.white : 'currentColor'} />
        <path d={GOVDE} fill={TG.teal} />
      </g>
    </svg>
  )
}

/** Isaret + "Tailglass Analytics" yazisi. Renkler temaya uyar. */
export function TailglassLogo({ size = 28, compact, className, onDark }: { size?: number; compact?: boolean; className?: string; onDark?: boolean }) {
  return (
    <span className={cn('inline-flex items-center', onDark ? 'text-white' : 'text-ink', className)} style={{ gap: size * 0.32 }} title={PRODUCT}>
      <TailglassMark size={size} />
      {!compact && (
        <span className="wordmark leading-none whitespace-nowrap" style={{ fontSize: size * 0.66 }}>
          <span className="font-[620] tracking-[-0.025em]">Tailglass</span>
          <span className={cn('ml-[0.24em] font-[420] tracking-[-0.01em]', onDark ? 'text-white/55' : 'text-muted')}>Analytics</span>
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
