import { motion } from 'framer-motion'
import { LayoutDashboard, Users, type LucideIcon } from 'lucide-react'
import { AnimatedBackground } from '@/components/AnimatedBackground'
import type { Role } from '@/lib/types'

interface RoleSelectPageProps {
  onSelect: (role: Role) => void
  onOpenSettings: () => void
}

const roles: { id: Role; label: string; icon: LucideIcon }[] = [
  { id: 'yonetici', label: 'Yönetici Girişi', icon: LayoutDashboard },
  { id: 'satis', label: 'Satış ve Muhasebe', icon: Users },
]

export function RoleSelectPage({ onSelect, onOpenSettings }: RoleSelectPageProps) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center gap-12 overflow-hidden px-4">
      <AnimatedBackground />
      <motion.h1
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="font-display relative text-3xl italic text-white/90"
      >
        Nasıl devam etmek istersiniz?
      </motion.h1>
      <div className="relative flex flex-col gap-8 sm:flex-row sm:gap-12">
        {roles.map(({ id, label, icon: Icon }, i) => (
          <motion.button
            key={id}
            initial={{ opacity: 0, y: 24, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.45, delay: i * 0.12, ease: 'easeOut' }}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onSelect(id)}
            className="group flex h-48 w-48 flex-col items-center justify-center gap-3 rounded-full border border-white/15 bg-white/10 text-white/85 backdrop-blur-md shadow-[0_12px_40px_rgba(0,0,0,0.25)] transition-colors hover:border-brand/50 hover:bg-white/15 hover:text-brand"
          >
            <Icon className="h-10 w-10 text-brand transition-transform group-hover:scale-110" strokeWidth={1.5} />
            <span className="px-4 text-center text-sm font-medium">{label}</span>
          </motion.button>
        ))}
      </div>
      <motion.button
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        onClick={onOpenSettings}
        className="relative text-base font-medium text-white/40 transition-colors hover:text-white/70"
      >
        ⚙ Ayarlar
      </motion.button>
    </div>
  )
}
