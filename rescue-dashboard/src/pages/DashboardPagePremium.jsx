import { useState } from 'react'
import { getStats, getWeather } from '../api/admin'
import { getResponseTimes } from '../api/analytics'
import { usePolling } from '../hooks/usePolling'
import { Header } from '../components/layout/Header'
import { StatCard, MetricCard } from '../components/ui/Card'

export function DashboardPagePremium() {
  const [stats, setStats] = useState(null)
  const [weather, setWeather] = useState([])
  const [responseTimes, setResponseTimes] = useState(null)
  const [apiHealthy, setApiHealthy] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [s, w, rt] = await Promise.all([getStats(), getWeather(), getResponseTimes(7)])
      setStats(s)
      setWeather(w)
      setResponseTimes(rt)
      setApiHealthy(true)
      setLoading(false)
    } catch {
      setApiHealthy(false)
      setLoading(false)
    }
  }
  usePolling(load, 30000)

  return (
    <div>
      <Header title="Dashboard" subtitle="Real-time overview of marine operations" />
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard 
          label="Active SOS Alerts" 
          value={stats?.active_sos_count} 
          icon="🆘" 
          color="red"
          loading={loading}
        />
        <StatCard 
          label="Active Fishing Trips" 
          value={stats?.active_trips_count} 
          icon="⛵" 
          color="blue"
          loading={loading}
        />
        <StatCard 
          label="Registered Fishermen" 
          value={stats?.fishermen_count} 
          icon="👨🦱" 
          color="green"
          loading={loading}
        />
        <StatCard 
          label="Critical Weather Zones" 
          value={stats?.critical_weather_count} 
          icon="⛈️" 
          color="yellow"
          loading={loading}
        />
      </div>

      {weather.length > 0 && (
        <div className="mb-8">
          <h2 className="text-white font-bold text-xl mb-4 flex items-center gap-2">
            <span>🌊</span>
            Active Weather Alerts
            <span className="text-sm font-normal text-slate-400 ml-2">({weather.length})</span>
          </h2>
          <div className="grid gap-4">
            {weather.map(w => (
              <div key={w.id} className={`
                rounded-2xl p-5 border backdrop-blur-sm
                transition-all duration-300 hover:shadow-xl
                ${
                  w.severity === 'danger' 
                    ? 'border-coral-500/40 bg-gradient-to-br from-red-500/10 to-red-600/5 hover:border-red-500/60' 
                    : w.severity === 'warning'
                    ? 'border-amber-500/40 bg-gradient-to-br from-yellow-500/10 to-yellow-600/5 hover:border-yellow-500/60'
                    : 'border-blue-500/40 bg-gradient-to-br from-blue-500/10 to-blue-600/5 hover:border-blue-500/60'
                }
              `}>
                <div className="flex items-start gap-4">
                  <span className="text-3xl">
                    {w.severity === 'danger' ? '🔴' : w.severity === 'warning' ? '🟡' : '🔵'}
                  </span>
                  <div className="flex-1">
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="text-white font-bold text-lg">{w.title}</h3>
                      <span className={`
                        px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide
                        ${
                          w.severity === 'danger' ? 'bg-red-500/20 text-red-300' :
                          w.severity === 'warning' ? 'bg-yellow-500/20 text-yellow-300' :
                          'bg-blue-500/20 text-blue-300'
                        }
                      `}>
                        {w.severity}
                      </span>
                    </div>
                    <p className="text-slate-300 text-sm mb-3">{w.description}</p>
                    <div className="flex flex-wrap gap-4 text-xs text-slate-400">
                      {w.source && (
                        <div className="flex items-center gap-1">
                          <span>📡</span>
                          <span>Source: {w.source}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-1">
                        <span>📍</span>
                        <span>Radius: {w.radius_km}km</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <span>🌊</span>
                        <span>{w.hazard_type?.replace('_', ' ')}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MetricCard
          title="System Health"
          icon="💚"
          metrics={[
            { label: 'API Status', value: apiHealthy === null ? 'Checking…' : apiHealthy ? 'Reachable' : 'Unreachable' },
            { label: 'Registered Fishermen', value: stats?.fishermen_count ?? 0 },
            { label: 'Active SOS', value: stats?.active_sos_count ?? 0 },
          ]}
        />
        <MetricCard
          title="Response Times (last 7 days)"
          icon="⚡"
          metrics={[
            { label: 'Average Response', value: responseTimes?.total_resolved ? `${responseTimes.average_response_minutes.toFixed(1)} min` : 'Not available' },
            { label: 'Fastest Response', value: responseTimes?.total_resolved ? `${responseTimes.min_response_minutes.toFixed(1)} min` : 'Not available' },
            { label: 'Alerts Resolved', value: responseTimes?.total_resolved ?? 0 },
          ]}
        />
      </div>
    </div>
  )
}
