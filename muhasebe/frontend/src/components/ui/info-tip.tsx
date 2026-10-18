import type { ReactNode } from 'react'
import { Info } from 'lucide-react'
import { cn } from '@/lib/cn'

interface InfoTipProps {
  children: ReactNode
  className?: string
  /** Varsayılan sola hizalı açılır; kartın kenarına yakın etiketlerde taşmayı önlemek için. */
  align?: 'left' | 'right'
}

// Teknik olmayan yöneticiler için: "Risk Altındaki Gelir" gibi terimlerin
// nasıl hesaplandığını üstüne gelince gösteren küçük bilgi ipucu. Native
// `title` yerine kendi bileşenimiz var çünkü sistem tooltip'i çok satırlı
// açıklama için okunaksız kalıyor ve gecikmesi/stili kontrol edilemiyor.
export function InfoTip({ children, className, align = 'left' }: InfoTipProps) {
  return (
    <span className={cn('group relative inline-flex', className)}>
      <button
        type="button"
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-black/30 transition-colors hover:text-brand-dark focus-visible:text-brand-dark focus-visible:outline-none dark:text-white/30 dark:hover:text-brand dark:focus-visible:text-brand"
        aria-label="Açıklama"
      >
        <Info className="h-3.5 w-3.5" strokeWidth={1.75} />
      </button>
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute bottom-full z-20 mb-2 w-72 rounded-lg border border-black/10 bg-white/95 px-3.5 py-2.5 text-xs font-normal normal-case leading-relaxed text-black/70 opacity-0 shadow-lg backdrop-blur-sm transition-opacity duration-100 group-hover:opacity-100 group-focus-within:opacity-100 dark:border-white/10 dark:bg-neutral-900/95 dark:text-white/70',
          align === 'left' ? 'left-0' : 'right-0'
        )}
      >
        {children}
      </span>
    </span>
  )
}
