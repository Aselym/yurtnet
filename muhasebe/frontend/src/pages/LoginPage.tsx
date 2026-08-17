import { useState, type FormEvent } from 'react'
import { motion } from 'framer-motion'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { AnimatedBackground } from '@/components/AnimatedBackground'
import { login } from '@/lib/auth'

interface LoginPageProps {
  onSuccess: () => void
}

export function LoginPage({ onSuccess }: LoginPageProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    const result = await login(username, password)
    setSubmitting(false)
    if (result.success) {
      onSuccess()
    } else {
      setError(result.message)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4">
      <AnimatedBackground />
      <motion.div
        initial={{ opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="relative"
      >
        <Card className="w-full max-w-[380px] border-white/15 bg-white/10 p-8 backdrop-blur-md">
          <div className="mb-8 flex flex-col items-center text-center">
            <img src="/static/images/logo-dark.png" alt="Piramit Bilgisayar" className="mb-4 h-12" />
            <h1 className="font-display text-2xl italic text-white">Piramit Lisans Takip</h1>
            <p className="mt-1 text-sm tracking-wide text-white/60">
              Analiz &amp; Takip Platformu
            </p>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 rounded-lg bg-red-500/15 px-3.5 py-2.5 text-sm text-red-300"
            >
              {error}
            </motion.div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-white/70">
                Kullanıcı Adı
              </label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                required
                autoFocus
                className="border-white/20 bg-white/10 text-white placeholder:text-white/40 focus:border-brand focus:ring-brand/30"
              />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium text-white/70">
                Şifre
              </label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="border-white/20 bg-white/10 text-white placeholder:text-white/40 focus:border-brand focus:ring-brand/30"
              />
            </div>
            <Button type="submit" size="lg" className="mt-2 w-full" disabled={submitting}>
              {submitting ? 'Giriş yapılıyor...' : 'Giriş Yap'}
            </Button>
          </form>
        </Card>
      </motion.div>
    </div>
  )
}
