import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import '@fontsource/gowun-batang/400.css'
import '@fontsource/gowun-batang/700.css'
import '@fontsource/gaegu/400.css'
import '@fontsource/gaegu/700.css'
import './styles/tokens.css'
import './styles/patterns.css'
import './styles/fabric.css'
import './styles/buttons.css'
import './index.css'
import { BrowserRouter } from 'react-router'
import App from './App.tsx'
import { TripProvider } from './store/trip'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <TripProvider>
        <App />
      </TripProvider>
    </BrowserRouter>
  </StrictMode>,
)
