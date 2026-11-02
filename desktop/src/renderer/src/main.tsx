import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initLang } from './state/useLang'
import { initTheme } from './state/useTheme'
import './styles/tokens.css'
import './styles/base.css'

initTheme()
initLang()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
