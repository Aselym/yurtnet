import { lazy, Suspense, useEffect, useState } from 'react'
import { api, setUnauthorizedHandler } from './lib/api'
import { useRoute } from './lib/router'
import { StateProvider } from './lib/state'
import { Shell } from './components/Shell'
import { Loading, Toaster } from './components/ui'
import { LoginPage } from './pages/LoginPage'

const Overview = lazy(() => import('./pages/Overview'))
const Movements = lazy(() => import('./pages/Movements'))
const Stock = lazy(() => import('./pages/Stock'))
const Customers = lazy(() => import('./pages/Customers'))
const Analysis = lazy(() => import('./pages/Analysis'))
const PeriodReport = lazy(() => import('./pages/PeriodReport'))
const Licenses = lazy(() => import('./pages/Licenses'))
const Subscriptions = lazy(() => import('./pages/Subscriptions'))
const Offers = lazy(() => import('./pages/Offers'))
const Reps = lazy(() => import('./pages/Reps'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

type Auth = 'checking' | 'in' | 'out'

export default function App() {
  const [auth, setAuth] = useState<Auth>('checking')

  useEffect(() => {
    setUnauthorizedHandler(() => setAuth('out'))
    api.get('/api/check-auth').then(() => setAuth('in'), () => setAuth('out'))
  }, [])

  if (auth === 'checking') return <Loading label="Açılıyor" className="h-full" />
  if (auth === 'out') return <><LoginPage onLogin={() => setAuth('in')} /><Toaster /></>

  return (
    <StateProvider>
      <Routed onLogout={async () => {
        try { await api.post('/api/logout') } catch { /* yok say */ }
        setAuth('out')
      }} />
      <Toaster />
    </StateProvider>
  )
}

function Routed({ onLogout }: { onLogout: () => void }) {
  const { page, params } = useRoute()
  const sayfa = (() => {
    switch (page) {
      case 'satislar': return <Movements key="satis" direction="SATIS_NET" />
      case 'alislar': return <Movements key="alis" direction="ALIS_NET" />
      case 'stok': return <Stock />
      case 'musteriler': return <Customers />
      case 'analiz': return <Analysis params={params} />
      case 'donem': return <PeriodReport />
      case 'lisanslar': return <Licenses params={params} />
      case 'abonelikler': return <Subscriptions />
      case 'teklifler': return <Offers />
      case 'temsilciler': return <Reps />
      case 'ayarlar': return <SettingsPage />
      default: return <Overview />
    }
  })()
  return (
    <Shell page={page} onLogout={onLogout}>
      <Suspense fallback={<Loading />}>{sayfa}</Suspense>
    </Shell>
  )
}
