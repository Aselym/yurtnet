import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

try {
  if (localStorage.getItem('defter.tema') === 'koyu') document.documentElement.setAttribute('data-theme', 'dark')
} catch { /* yok say */ }

// Sunucuda yeni surum kurulduysa acik sekme eski parca dosyalarini ister ve
// bulamaz; sayfayi bir kez yenileyip yeni surume gecir (dongu korumali).
window.addEventListener('vite:preloadError', (e) => {
  try {
    const son = Number(sessionStorage.getItem('defter.yenilendi') || 0)
    if (Date.now() - son < 10000) return
    sessionStorage.setItem('defter.yenilendi', String(Date.now()))
  } catch { /* yok say */ }
  e.preventDefault()
  window.location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
