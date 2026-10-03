import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { applyCompanyDocumentBrand } from './lib/branding'
import { loadRuntimeConfig } from './lib/api'
import App from './App'
import './styles.css'

applyCompanyDocumentBrand()

const rootElement = document.getElementById('root')
if (!rootElement) throw new Error('Agent5 root element is missing')

void loadRuntimeConfig().finally(() => {
  createRoot(rootElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
})
