import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import './styles/fonts.css'
import './styles/tokens.css'
import './styles/patterns.css'
import './styles/fabric.css'
import './styles/buttons.css'
import './styles/chips.css'
import './index.css'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'
import { AuthProvider } from './store/auth'
import { TripProvider } from './store/trip'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <TripProvider>
          <App />
        </TripProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
