import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

try {
  if (localStorage.getItem('defter.tema') === 'koyu') document.documentElement.setAttribute('data-theme', 'dark')
} catch { /* yok say */ }

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
