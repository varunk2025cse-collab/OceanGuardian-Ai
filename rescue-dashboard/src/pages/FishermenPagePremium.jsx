import { useState } from 'react'
import { getFishermen } from '../api/admin'
import { Header } from '../components/layout/Header'
import { usePolling } from '../hooks/usePolling'
import { Card } from '../components/ui/Card'
import { timeAgo } from '../utils/formatters'

function RiskBadge({ score, label }) {
  // Safety semantics audit finding (Final Release Engineering Phase G):
  // this used to fall back to the "safe" (teal) style for any unrecognized
  // label — including "unknown" (no location data at all), which silently
  // presented an absence of data as a safety claim. "unknown" now has its
  // own neutral style and is the explicit fallback, never "safe".
  const colors = {
    safe: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
    caution: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    danger: 'bg-red-500/20 text-red-300 border-red-500/30',
    unknown: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  }
  return (
    <span className={`px-2 py-1 rounded-lg text-xs font-bold uppercase border ${colors[label] || colors.unknown}`}>
      {label}{score >= 0 ? ` (${score})` : ''}
    </span>
  )
}

function FishermanCard({ fisherman }) {
  return (
    <Card className="p-6 hover:scale-[1.02] transition-transform cursor-pointer">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-white font-bold text-lg mb-1">{fisherman.full_name}</h3>
          <div className="flex items-center gap-2 text-slate-400 text-sm">
            <span>📞</span>
            <span>{fisherman.phone_number}</span>
          </div>
        </div>
        {fisherman.active_sos && (
          <span className="px-3 py-1 bg-red-500/20 text-red-300 rounded-full text-xs font-bold animate-pulse">
            SOS ACTIVE
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-slate-500 text-xs uppercase mb-1">Boat</div>
          <div className="text-white text-sm font-medium">{fisherman.boat_name || '—'}</div>
        </div>
        <div>
          <div className="text-slate-500 text-xs uppercase mb-1">Harbor</div>
          <div className="text-white text-sm font-medium">{fisherman.home_harbor || '—'}</div>
        </div>
      </div>

      {fisherman.last_location && (
        <div className="mb-4 p-3 bg-slate-900/50 rounded-lg">
          <div className="text-slate-500 text-xs uppercase mb-1">Last Known Position</div>
          <div className="text-slate-300 text-sm font-mono">
            {fisherman.last_location.latitude.toFixed(4)}, {fisherman.last_location.longitude.toFixed(4)}
          </div>
          <div className="text-slate-500 text-xs mt-1">
            {timeAgo(fisherman.last_location.recorded_at)}
          </div>
        </div>
      )}

      {fisherman.active_trip && (
        <div className="mb-4 p-3 bg-primary-500/10 border border-primary-500/30 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <span>⛵</span>
            <span className="text-primary-300 text-sm font-semibold">Active Trip</span>
          </div>
          <div className="text-slate-400 text-xs">
            {fisherman.active_trip.destination || 'Fishing grounds'}
          </div>
          {fisherman.active_trip.boat_name && (
            <div className="text-slate-500 text-xs mt-1">
              Boat: {fisherman.active_trip.boat_name}
            </div>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-4 border-t border-slate-700">
        <RiskBadge score={fisherman.risk_score} label={fisherman.risk_label} />
        {fisherman.emergency_contact_phone && (
          <div className="text-slate-500 text-xs">
            Emergency: {fisherman.emergency_contact_phone}
          </div>
        )}
      </div>
    </Card>
  )
}

export function FishermenPagePremium() {
  const [fishermen, setFishermen] = useState([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const data = await getFishermen({ limit: 100 })
      setFishermen(data.items)
      setTotal(data.total)
      setLoading(false)
    } catch {}
  }
  usePolling(load, 30000)

  const filtered = fishermen.filter(f => {
    if (!search) return true
    const s = search.toLowerCase()
    return f.full_name?.toLowerCase().includes(s) ||
           f.phone_number?.includes(s) ||
           f.boat_name?.toLowerCase().includes(s) ||
           f.home_harbor?.toLowerCase().includes(s)
  })

  return (
    <div>
      <Header title="Fishermen Directory" subtitle="All registered fishermen and their status">
        <span className="px-3 py-1.5 bg-slate-800 rounded-lg text-slate-400 text-sm font-medium">
          {total} registered
        </span>
      </Header>

      <div className="mb-6">
        <div className="relative">
          <input
            type="text"
            placeholder="Search by name, phone, boat, or harbor..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-4 py-3 pl-11 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
          />
          <span className="absolute left-3 top-3.5 text-slate-400 text-lg">🔍</span>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-6 bg-slate-700 rounded w-3/4 mb-4"></div>
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-6"></div>
              <div className="h-20 bg-slate-700 rounded mb-4"></div>
              <div className="h-4 bg-slate-700 rounded w-1/3"></div>
            </Card>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">🎣</div>
          <div className="text-slate-400 text-lg font-medium">No fishermen found</div>
          <div className="text-slate-500 text-sm mt-2">
            {search ? 'Try different search terms' : 'No registered fishermen yet'}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map(f => (
            <FishermanCard key={f.id} fisherman={f} />
          ))}
        </div>
      )}
    </div>
  )
}
