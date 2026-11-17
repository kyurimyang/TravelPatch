import { useSyncExternalStore } from 'react'
import './OfflineBanner.css'

// navigator.onLine as React state: the browser tells us through the online/offline events.
function subscribe(onChange: () => void) {
  window.addEventListener('online', onChange)
  window.addEventListener('offline', onChange)
  return () => {
    window.removeEventListener('online', onChange)
    window.removeEventListener('offline', onChange)
  }
}

export function OfflineBanner() {
  const online = useSyncExternalStore(subscribe, () => navigator.onLine, () => true)
  if (online) return null
  return (
    <div className="offline-banner" role="status">
      <b>인터넷이 끊겼어요.</b> 저장한 일정은 그대로 볼 수 있고, 새 패치는 연결되면 찾을 수 있어요.
    </div>
  )
}
