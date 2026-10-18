import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from 'react'
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
      <SayfaHatasi key={page}><Suspense fallback={<Loading />}>{sayfa}</Suspense></SayfaHatasi>
    </Shell>
  )
}

// Bir sayfa cokerse tum uygulama bos kalmasin: mesaj + yeniden yukle
class SayfaHatasi extends Component<{ children: ReactNode }, { hata: Error | null }> {
  state = { hata: null as Error | null }
  static getDerivedStateFromError(hata: Error) { return { hata } }
  render() {
    if (!this.state.hata) return this.props.children
    const surum = /dynamically imported module|Importing a module script/i.test(this.state.hata.message)
    return (
      <div className="panel mx-auto mt-10 max-w-lg p-6">
        <h2 className="text-[16px] font-semibold">{surum ? 'Uygulama güncellendi' : 'Bu sayfa açılırken bir sorun oluştu'}</h2>
        <p className="mt-1.5 text-[13.5px] text-ink-2">
          {surum ? 'Sunucuda yeni sürüm kurulmuş. Sayfayı yenileyince devam edebilirsiniz.' : 'Sayfayı yenilemek genellikle sorunu çözer. Tekrarlarsa sistem yöneticisine bu mesajı iletin: '}
          {!surum && <code className="text-[12px]">{this.state.hata.message}</code>}
        </p>
        <button onClick={() => window.location.reload()} className="mt-4 h-9 rounded-[var(--radius-ctl)] bg-brand px-3.5 text-sm font-medium text-white">Sayfayı yenile</button>
      </div>
    )
  }
}
