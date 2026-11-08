import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initLang } from './state/useLang'
import { initTheme } from './state/useTheme'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/cyrillic-400.css'
import '@fontsource/ibm-plex-sans/cyrillic-500.css'
import '@fontsource/ibm-plex-sans/cyrillic-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/cyrillic-400.css'
import '@fontsource/ibm-plex-mono/cyrillic-500.css'
import './styles/tokens.css'
import './styles/base.css'

initTheme()
initLang()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
