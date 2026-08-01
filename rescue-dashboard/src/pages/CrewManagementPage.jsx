import { useState, useCallback } from 'react'
import { usePolling } from '../hooks/usePolling'
import { getBoats, getBoatCrew, getBoatCrewStats } from '../api/boats'
import { Header } from '../components/layout/Header'
import { Card, StatCard, MetricCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

const ROLE_ICONS = {
  captain: '👨‍✈️', navigator: '🧭', engineer: '🔧', deckhand: '⚓',
  lookout: '👁️', medic: '🩺', owner: '🏠', other: '👤',
}
const ROLE_COLORS = {
  captain: 'blue', navigator: 'green', engineer: 'yellow', deckhand: 'blue',
  lookout: 'green', medic: 'red', owner: 'yellow', other: 'blue',
}

export function CrewManagementPage() {
  const [boats, setBoats] = useState([])
  const [selectedBoatId, setSelectedBoatId] = useState(null)
  const [crew, setCrew] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    try {
      const res = await getBoats({ page: 1, page_size: 100 })
      setBoats(res.data || [])
      setLoading(false)
      setError(null)
    } catch {
      setError('Failed to load fleet data')
      setLoading(false)
    }
  }, [])

  usePolling(load, 60000)

  const selectBoat = async (boatId) => {
    setSelectedBoatId(boatId)
    try {
      const [crewData, statsData] = await Promise.all([
        getBoatCrew(boatId, { include_inactive: false }),
        getBoatCrewStats(boatId),
      ])
      setCrew(crewData || [])
      setStats(statsData)
    } catch {
      setCrew([])
      setStats(null)
    }
  }

  const filteredCrew = crew.filter(m =>
    m.full_name.toLowerCase().includes(search.toLowerCase()) ||
    m.role.toLowerCase().includes(search.toLowerCase())
  )

  // Aggregate crew stats across all boats
  const totalCrew = boats.length > 0 ? '—' : 0
  const selectedBoat = boats.find(b => b.id === selectedBoatId)

  return (
    <div>
      <Header title="Crew Management" subtitle="Personnel directory, assignments, roles & emergency contacts — live backend data" />

      {error && (
        <Card className="p-4 mb-6 border-amber-500/40 bg-amber-500/10">
          <span className="text-amber-300 text-sm">{error}</span>
        </Card>
      )}

      {/* Fleet selector */}
      <Card className="p-6 mb-6">
        <h3 className="text-white font-bold text-lg mb-4">Select Vessel</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 bg-slate-700/50 rounded-xl animate-pulse" />
            ))
          ) : boats.length === 0 ? (
            <p className="text-slate-400 col-span-full">No boats registered in the fleet.</p>
          ) : (
            boats.map(b => (
              <button
                key={b.id}
                onClick={() => selectBoat(b.id)}
                className={`p-4 rounded-xl text-left transition-all border ${
                  selectedBoatId === b.id
                    ? 'bg-primary-600/20 border-primary-500 shadow-lg shadow-primary-500/10'
                    : 'bg-slate-800/50 border-slate-700/50 hover:border-primary-500/40'
                }`}
              >
                <div className="text-white font-bold text-sm truncate">🚤 {b.name}</div>
                <div className="text-slate-400 text-xs mt-1">{b.registration_number || 'No reg.'}</div>
              </button>
            ))
          )}
        </div>
      </Card>

      {selectedBoatId && (
        <>
          {/* Stats row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
            <StatCard label="Active Crew" value={stats?.total_active ?? '—'} icon="👥" color="blue" />
            <StatCard label="Captain Assigned" value={stats?.has_captain ? '✅ Yes' : '❌ No'} icon="👨‍✈️" color={stats?.has_captain ? 'green' : 'red'} />
            <StatCard label="Primary Contact" value={stats?.has_primary_contact ? '✅ Set' : '⚠️ Missing'} icon="📞" color={stats?.has_primary_contact ? 'green' : 'yellow'} />
            <StatCard label="Roles Covered" value={stats?.roles_filled ?? '—'} icon="🎭" color="green" />
          </div>

          {/* Search */}
          <Card className="p-4 mb-6">
            <input
              type="text"
              placeholder="🔍 Search crew by name or role..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full bg-slate-900/50 text-white border border-slate-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary-500 transition-colors"
            />
          </Card>

          {/* Crew Table */}
          <Card className="overflow-hidden">
            <div className="p-6 border-b border-slate-700/50">
              <h3 className="text-white font-bold text-lg">
                Crew Roster — {selectedBoat?.name || `Boat #${selectedBoatId}`}
              </h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800/50 border-b border-slate-700/50">
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Crew Member</th>
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Role</th>
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Phone</th>
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Primary Contact</th>
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Status</th>
                    <th className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">Assigned</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCrew.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-slate-400">
                        {crew.length === 0 ? 'No crew members assigned to this vessel.' : 'No crew match your search.'}
                      </td>
                    </tr>
                  ) : (
                    filteredCrew.map(m => (
                      <tr key={m.id} className="border-b border-slate-700/30 hover:bg-slate-800/30 transition-colors">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary-500 to-teal-500 flex items-center justify-center text-lg">
                              {ROLE_ICONS[m.role] || '👤'}
                            </div>
                            <div>
                              <div className="text-white font-semibold text-sm">{m.full_name}</div>
                              {m.user_id && <div className="text-slate-500 text-xs">User #{m.user_id}</div>}
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <Badge color={ROLE_COLORS[m.role] || 'blue'} className="capitalize">{m.role.replace('_', ' ')}</Badge>
                        </td>
                        <td className="px-6 py-4 text-slate-300 text-sm">{m.phone_number || '—'}</td>
                        <td className="px-6 py-4">
                          {m.is_primary_contact
                            ? <span className="text-teal-400 font-semibold text-sm">✅ Primary</span>
                            : <span className="text-slate-500 text-sm">—</span>
                          }
                        </td>
                        <td className="px-6 py-4">
                          <Badge color={m.is_active ? 'green' : 'red'}>{m.is_active ? 'Active' : 'Removed'}</Badge>
                        </td>
                        <td className="px-6 py-4 text-slate-400 text-sm">
                          {m.assigned_at ? new Date(m.assigned_at).toLocaleDateString() : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Role Distribution */}
          {stats?.by_role && Object.keys(stats.by_role).length > 0 && (
            <Card className="p-6 mt-6">
              <h3 className="text-white font-bold text-lg mb-4">Role Distribution</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {Object.entries(stats.by_role).map(([role, count]) => (
                  <div key={role} className="bg-slate-900/50 rounded-xl p-4 text-center border border-slate-700/30">
                    <div className="text-2xl mb-2">{ROLE_ICONS[role] || '👤'}</div>
                    <div className="text-white font-bold text-lg">{count}</div>
                    <div className="text-slate-400 text-xs capitalize">{role.replace('_', ' ')}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
