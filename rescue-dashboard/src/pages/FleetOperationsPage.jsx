import { useState } from 'react'
import { getBoats, getFleetSummary } from '../api/boats'
import { Header } from '../components/layout/Header'
import { usePolling } from '../hooks/usePolling'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { BoatStatusBadge } from '../components/boats/BoatStatusBadge'
import { BoatDetailModal } from '../components/boats/BoatDetailModal'

export function FleetOperationsPage() {
  const [boats, setBoats] = useState([])
  const [summary, setSummary] = useState(null)
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedBoatId, setSelectedBoatId] = useState(null)

  const load = async () => {
    try {
      const [boatsData, summaryData] = await Promise.all([
        getBoats({ page_size: 100, search: search || undefined }),
        getFleetSummary()
      ])
      setBoats(boatsData.data)
      setTotal(boatsData.meta.total)
      setSummary(summaryData)
      setLoading(false)
    } catch (err) {
      console.error('Failed to load fleet data', err)
    }
  }

  // Poll every 30 seconds
  usePolling(load, 30000)

  return (
    <div>
      <Header title="Fleet Operations" subtitle="Enterprise vessel lifecycle & readiness">
        {summary && (
          <div className="flex gap-4">
            <div className="px-3 py-1.5 bg-slate-800 rounded-lg text-center">
              <div className="text-white font-bold text-lg leading-none">{summary.total_registered}</div>
              <div className="text-slate-400 text-[10px] uppercase font-semibold mt-1">Total Fleet</div>
            </div>
            <div className="px-3 py-1.5 bg-slate-800 rounded-lg text-center border border-green-500/30">
              <div className="text-green-400 font-bold text-lg leading-none">{summary.total_active}</div>
              <div className="text-green-500/70 text-[10px] uppercase font-semibold mt-1">Active</div>
            </div>
            <div className="px-3 py-1.5 bg-slate-800 rounded-lg text-center border border-yellow-500/30">
              <div className="text-yellow-400 font-bold text-lg leading-none">{summary.total_maintenance}</div>
              <div className="text-yellow-500/70 text-[10px] uppercase font-semibold mt-1">Maintenance</div>
            </div>
          </div>
        )}
      </Header>

      <div className="mb-6">
        <div className="relative">
          <input
            type="text"
            placeholder="Search boats by name or registration number..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load()}
            className="w-full px-4 py-3 pl-11 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-400 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
          />
          <span className="absolute left-3 top-3.5 text-slate-400 text-lg">🔍</span>
          <Button 
            className="absolute right-2 top-2"
            size="sm"
            onClick={load}
          >
            Search
          </Button>
        </div>
      </div>

      {loading && boats.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="flex justify-between mb-4">
                <div className="h-6 bg-slate-700 rounded w-1/2"></div>
                <div className="h-6 bg-slate-700 rounded w-1/4"></div>
              </div>
              <div className="h-4 bg-slate-700 rounded w-1/3 mb-6"></div>
              <div className="h-12 bg-slate-700 rounded"></div>
            </Card>
          ))}
        </div>
      ) : boats.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">🚤</div>
          <div className="text-slate-400 text-lg font-medium">No boats found</div>
          <div className="text-slate-500 text-sm mt-2">
            {search ? 'Try adjusting your search filters' : 'The fleet is currently empty'}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {boats.map(boat => (
            <Card 
              key={boat.id} 
              className="p-5 hover:scale-[1.02] transition-transform cursor-pointer border hover:border-primary-500/50"
              onClick={() => setSelectedBoatId(boat.id)}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="pr-2">
                  <h3 className="text-white font-bold text-lg truncate" title={boat.name}>{boat.name}</h3>
                  <div className="text-slate-400 text-xs font-mono mt-0.5">{boat.registration_number || 'No Reg'}</div>
                </div>
                <BoatStatusBadge status={boat.status} />
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4 mt-4">
                <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-700/50">
                  <div className="text-slate-500 text-[10px] uppercase font-bold mb-1">Class</div>
                  <div className="text-slate-300 text-sm truncate">{boat.vessel_class || '—'}</div>
                </div>
                <div className="bg-slate-900/50 p-2 rounded-lg border border-slate-700/50">
                  <div className="text-slate-500 text-[10px] uppercase font-bold mb-1">Engine</div>
                  <div className="text-slate-300 text-sm truncate">{boat.engine_type || '—'}</div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-slate-700/50">
                <div className="text-xs font-medium px-2 py-1 rounded bg-slate-800 text-slate-300">
                  Owner: User #{boat.owner_id}
                </div>
                {boat.verification_status === 'verified' ? (
                  <span className="text-green-400 text-xs font-bold flex items-center gap-1">
                    <span>✓</span> Verified
                  </span>
                ) : (
                  <span className="text-yellow-500 text-xs font-bold">
                    Pending Verification
                  </span>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {selectedBoatId && (
        <BoatDetailModal 
          boatId={selectedBoatId} 
          onClose={() => setSelectedBoatId(null)} 
        />
      )}
    </div>
  )
}
