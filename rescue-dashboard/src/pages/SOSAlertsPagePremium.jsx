import { useState } from 'react'
import { getSOS } from '../api/admin'
import { SOSStatusBadge } from '../components/sos/SOSStatusBadge'
import { SOSDetailModal } from '../components/sos/SOSDetailModal'
import { Header } from '../components/layout/Header'
import { usePolling } from '../hooks/usePolling'
import { Button } from '../components/ui/Button'
import { fmtCoords, timeAgo } from '../utils/formatters'

const FILTERS = ['all', 'active', 'acknowledged', 'resolved', 'false_alarm']

function PriorityBadge({ priority }) {
  const colors = {
    low: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
    medium: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    high: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    critical: 'bg-red-500/20 text-red-300 border-red-500/30 animate-pulse',
  }
  return (
    <span className={`px-2 py-1 rounded-lg text-xs font-bold uppercase border ${colors[priority] || colors.high}`}>
      {priority}
    </span>
  )
}

function SearchBar({ value, onChange }) {
  return (
    <div className="relative">
      <input
        type="text"
        placeholder="Search by fisherman name, boat, location..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-4 py-3 pl-11 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
      />
      <span className="absolute left-3 top-3.5 text-slate-400 text-lg">🔍</span>
    </div>
  )
}

export function SOSAlertsPagePremium({ onCountChange }) {
  const [alerts, setAlerts] = useState([])
  const [total, setTotal] = useState(0)
  const [filter, setFilter] = useState('active')
  const [selected, setSelected] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const params = filter !== 'all' ? { status: filter, limit: 100 } : { limit: 100 }
      const data = await getSOS(params)
      setAlerts(data.items)
      setTotal(data.total)
      setLoading(false)
      if (filter === 'active') onCountChange?.(data.total)
    } catch {}
  }
  usePolling(load, 20000)

  const handleUpdated = (updated) => {
    setAlerts(prev => prev.map(a => a.id === updated.id ? updated : a))
  }

  const filteredAlerts = alerts.filter(a => {
    if (!search) return true
    const s = search.toLowerCase()
    return a.fisherman?.full_name?.toLowerCase().includes(s) ||
           a.fisherman?.boat_name?.toLowerCase().includes(s) ||
           a.message?.toLowerCase().includes(s)
  })

  return (
    <div>
      <Header title="SOS Alerts" subtitle="Emergency distress signals from fishermen">
        <div className="flex items-center gap-3">
          <span className="px-3 py-1.5 bg-slate-800 rounded-lg text-slate-400 text-sm font-medium">
            {total} total
          </span>
          {filter === 'active' && total > 0 && (
            <span className="px-3 py-1.5 bg-red-500/20 rounded-lg text-red-300 text-sm font-bold animate-pulse">
              {total} ACTIVE
            </span>
          )}
        </div>
      </Header>

      <div className="mb-6 space-y-4">
        <SearchBar value={search} onChange={setSearch} />

        <div className="flex gap-2 bg-slate-800/50 p-1.5 rounded-xl border border-slate-700 w-fit">
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`
                px-4 py-2 rounded-lg text-sm font-semibold capitalize transition-all
                ${filter === f 
                  ? 'bg-primary-600 text-white shadow-lg' 
                  : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }
              `}
            >
              {f.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="bg-slate-800/50 rounded-2xl border border-slate-700 p-12 text-center">
          <div className="inline-block animate-spin text-4xl mb-4">⚓</div>
          <div className="text-slate-400">Loading alerts...</div>
        </div>
      ) : (
        <div className="bg-slate-800/50 rounded-2xl border border-slate-700 overflow-hidden backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-slate-400 text-xs uppercase tracking-wide border-b border-slate-700 bg-slate-900/50">
                  <th className="text-left px-6 py-4 font-bold">Priority</th>
                  <th className="text-left px-6 py-4 font-bold">Status</th>
                  <th className="text-left px-6 py-4 font-bold">Fisherman</th>
                  <th className="text-left px-6 py-4 font-bold hidden md:table-cell">Location</th>
                  <th className="text-left px-6 py-4 font-bold">Time</th>
                  <th className="text-left px-6 py-4 font-bold">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredAlerts.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-16">
                      <div className="text-6xl mb-4">🌊</div>
                      <div className="text-slate-400 text-lg font-medium">No alerts found</div>
                      <div className="text-slate-500 text-sm mt-2">
                        {search ? 'Try different search terms' : 'All clear on the water'}
                      </div>
                    </td>
                  </tr>
                )}
                {filteredAlerts.map(a => (
                  <tr
                    key={a.id}
                    className={`
                      border-b border-slate-700/50 hover:bg-slate-700/20 transition-colors cursor-pointer
                      ${a.status === 'active' ? 'bg-red-500/5' : ''}
                    `}
                    onClick={() => setSelected(a)}
                  >
                    <td className="px-6 py-4">
                      <PriorityBadge priority={a.priority || 'high'} />
                    </td>
                    <td className="px-6 py-4">
                      <SOSStatusBadge status={a.status} />
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-white font-semibold">{a.fisherman?.full_name}</div>
                      <div className="text-slate-400 text-sm">{a.fisherman?.boat_name || '—'}</div>
                    </td>
                    <td className="px-6 py-4 hidden md:table-cell font-mono text-slate-300 text-sm">
                      {fmtCoords(a.latitude, a.longitude)}
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-sm whitespace-nowrap">
                      {timeAgo(a.triggered_at)}
                    </td>
                    <td className="px-6 py-4">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelected(a)
                        }}
                      >
                        View Details
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selected && (
        <SOSDetailModal
          alert={selected}
          onClose={() => setSelected(null)}
          onUpdated={handleUpdated}
        />
      )}
    </div>
  )
}
