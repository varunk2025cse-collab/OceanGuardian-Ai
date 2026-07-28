import { useEffect, useState } from 'react'
import api from '../../api/client'

/**
 * Persistent banner shown whenever the backend reports demo/simulation
 * mode for any provider — GET /api/v1/system-info (unauthenticated,
 * no secrets). Final Release Engineering Phase C/G: simulated data must
 * never be visually indistinguishable from real data.
 */
export function SystemModeBanner() {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .get('/system-info')
      .then((r) => {
        if (!cancelled) setInfo(r.data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (!info) return null

  const simulatedBits = []
  if (info.demo_mode) simulatedBits.push('DEMO MODE')
  if (info.notification_provider?.startsWith('simulation')) simulatedBits.push('notifications simulated')
  if (info.weather_provider === 'simulated') simulatedBits.push('weather simulated')
  if (info.ai_provider?.includes('falling back')) simulatedBits.push('AI explanation is template-based (no LLM configured)')

  if (simulatedBits.length === 0) return null

  return (
    <div className="bg-amber-500/15 border-b border-amber-500/40 text-amber-200 text-xs px-4 py-2 flex items-center gap-2">
      <span className="font-bold uppercase tracking-wide">⚠ {simulatedBits.join(' · ')}</span>
      <span className="text-amber-300/70">— this reflects real system data, but with the noted integration(s) not connected to a live provider.</span>
    </div>
  )
}
