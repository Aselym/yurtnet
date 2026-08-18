import { useCallback, useEffect, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { LoginPage } from '@/pages/LoginPage'
import { RoleSelectPage } from '@/pages/RoleSelectPage'
import { LoadingTransition } from '@/pages/LoadingTransition'
import { AdminDashboardPage } from '@/pages/AdminDashboardPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { checkAuth, logout } from '@/lib/auth'
import type { Role } from '@/lib/types'

type Step = 'checking' | 'login' | 'role-select' | 'transition' | 'panel' | 'settings'

const ROLE_STORAGE_KEY = 'piramit.rol'

export default function App() {
  const [step, setStep] = useState<Step>('checking')
  const [role, setRole] = useState<Role | null>(null)

  useEffect(() => {
    let cancelled = false
    checkAuth().then((authenticated) => {
      if (cancelled) return
      if (!authenticated) {
        setStep('login')
        return
      }
      const storedRole = sessionStorage.getItem(ROLE_STORAGE_KEY) as Role | null
      if (storedRole === 'yonetici' || storedRole === 'satis') {
        setRole(storedRole)
        setStep('panel')
      } else {
        setStep('role-select')
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const handleLoginSuccess = useCallback(() => setStep('role-select'), [])

  const handleRoleSelect = useCallback((selected: Role) => {
    sessionStorage.setItem(ROLE_STORAGE_KEY, selected)
    setRole(selected)
    setStep('transition')
  }, [])

  const handleTransitionDone = useCallback(() => setStep('panel'), [])

  const handleOpenSettings = useCallback(() => setStep('settings'), [])
  const handleCloseSettings = useCallback(() => setStep('role-select'), [])

  const handleLogout = useCallback(async () => {
    await logout()
    sessionStorage.removeItem(ROLE_STORAGE_KEY)
    setRole(null)
    setStep('login')
  }, [])

  return (
    <AnimatePresence mode="wait">
      {step === 'checking' && <div key="checking" className="min-h-screen bg-bg dark:bg-neutral-950" />}
      {step === 'login' && <LoginPage key="login" onSuccess={handleLoginSuccess} />}
      {step === 'role-select' && (
        <RoleSelectPage key="role-select" onSelect={handleRoleSelect} onOpenSettings={handleOpenSettings} />
      )}
      {step === 'transition' && <LoadingTransition key="transition" onDone={handleTransitionDone} />}
      {step === 'panel' && role === 'satis' && (
        <DashboardPage key="panel-satis" onLogout={handleLogout} />
      )}
      {step === 'panel' && role === 'yonetici' && (
        <AdminDashboardPage key="panel-yonetici" onLogout={handleLogout} />
      )}
      {step === 'settings' && <SettingsPage key="settings" onBack={handleCloseSettings} />}
    </AnimatePresence>
  )
}
