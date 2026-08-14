import { useEffect } from 'react'
import { motion } from 'framer-motion'

interface LoadingTransitionProps {
  onDone: () => void
  durationMs?: number
}

export function LoadingTransition({ onDone, durationMs = 3000 }: LoadingTransitionProps) {
  useEffect(() => {
    const timer = setTimeout(onDone, durationMs)
    return () => clearTimeout(timer)
  }, [onDone, durationMs])

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg dark:bg-neutral-950"
    >
      <motion.img
        src="/static/images/logo.png"
        alt="Piramit Bilgisayar"
        className="h-14"
        animate={{ scale: [1, 1.06, 1] }}
        transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
      />
      <div className="relative h-1 w-56 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-brand"
          initial={{ width: '0%' }}
          animate={{ width: '100%' }}
          transition={{ duration: durationMs / 1000, ease: 'easeInOut' }}
        />
      </div>
      <p className="text-sm text-black/50 dark:text-white/50">Panele hazırlanıyor...</p>
    </motion.div>
  )
}
