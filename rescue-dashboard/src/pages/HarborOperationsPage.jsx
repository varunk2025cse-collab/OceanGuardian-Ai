import { useState } from 'react'
import { getHarbors } from '../api/harbors'
import { Header } from '../components/layout/Header'
import { usePolling } from '../hooks/usePolling'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { HarborDetailModal } from '../components/harbors/HarborDetailModal'
import { HarborFeatureBadge } from '../components/harbors/HarborFeatureBadge'

export function HarborOperationsPage() {
  const [harbors, setHarbors] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selectedHarborId, setSelectedHarborId] = useState(null)
  const [typeFilter, setTypeFilter] = useState('')

  const load = async () => {
    try {
      const data = await getHarbors({ 
        limit: 100, 
        harbor_type: typeFilter || undefined 
      })
      setHarbors(data.harbors || [])
      setTotal(data.total || 0)
      setLoading(false)
    } catch (err) {
      console.error('Failed to load harbors data', err)
      setLoading(false)
    }
  }

  // Poll every 60 seconds (harbors don't change as rapidly as trips/sos)
  usePolling(load, 60000)

  const activeFeatures = (h) => {
    return [
      h.fuel_availability && 'Fuel',
      h.medical_facility && 'Medical',
      h.repair_facility && 'Repair',
      h.emergency_shelter && 'Shelter',
      h.ice_availability && 'Ice'
    ].filter(Boolean)
  }

  return (
    <div>
      <Header title="Harbor Operations" subtitle="Infrastructure intelligence and capacity monitoring">
        <div className="flex gap-4">
          <div className="px-3 py-1.5 bg-slate-800 rounded-lg text-center border border-slate-700">
            <div className="text-white font-bold text-lg leading-none">{total}</div>
            <div className="text-slate-400 text-[10px] uppercase font-semibold mt-1">Total Harbors</div>
          </div>
        </div>
      </Header>

      <div className="mb-6 flex gap-4">
        <select 
          className="bg-slate-800/80 border border-slate-700 rounded-xl text-white px-4 py-3 focus:outline-none focus:border-primary-500"
          value={typeFilter}
          onChange={(e) => {
            setTypeFilter(e.target.value)
            setLoading(true)
          }}
        >
          <option value="">All Types</option>
          <option value="major">Major Harbors</option>
          <option value="minor">Minor Harbors</option>
          <option value="emergency">Emergency Shelters</option>
        </select>
        <Button onClick={() => { setLoading(true); load(); }}>Refresh Registry</Button>
      </div>

      {loading && harbors.length === 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="h-6 bg-slate-700 rounded w-3/4 mb-2"></div>
              <div className="h-4 bg-slate-700 rounded w-1/2 mb-6"></div>
              <div className="flex gap-2 mb-2"><div className="h-4 bg-slate-700 rounded w-12"></div></div>
            </Card>
          ))}
        </div>
      ) : harbors.length === 0 ? (
        <div className="text-center py-16 bg-slate-800/50 rounded-xl border border-slate-700">
          <div className="text-6xl mb-4">⚓</div>
          <div className="text-slate-400 text-lg font-medium">No harbors found</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {harbors.map(harbor => (
            <Card 
              key={harbor.id} 
              className="p-5 hover:scale-[1.02] transition-transform cursor-pointer border hover:border-primary-500/50 flex flex-col"
              onClick={() => setSelectedHarborId(harbor.id)}
            >
              <div className="flex items-start justify-between mb-3 border-b border-slate-700/50 pb-3">
                <div>
                  <h3 className="text-white font-bold text-lg mb-1">{harbor.name}</h3>
                  <div className="text-slate-400 text-xs font-medium">
                    {harbor.district ? `${harbor.district}, ` : ''}{harbor.state}
                  </div>
                </div>
                {harbor.harbor_type && (
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    harbor.harbor_type === 'emergency' ? 'bg-red-500/20 text-red-400' :
                    harbor.harbor_type === 'major' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-slate-500/20 text-slate-400'
                  }`}>
                    {harbor.harbor_type}
                  </span>
                )}
              </div>

              <div className="flex-1">
                <div className="text-slate-500 text-xs mb-2">Available Services</div>
                <div className="flex flex-wrap gap-1.5 mb-4">
                  {activeFeatures(harbor).map(f => (
                    <span key={f} className="px-2 py-0.5 bg-slate-900 text-slate-300 rounded text-xs border border-slate-700">
                      {f}
                    </span>
                  ))}
                  {activeFeatures(harbor).length === 0 && (
                    <span className="text-slate-500 text-xs italic">Basic docking only</span>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-end pt-3 border-t border-slate-700/50 mt-auto">
                <div>
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Rating</div>
                  <div className="text-yellow-400 text-sm font-bold">
                    {harbor.average_rating > 0 ? `${harbor.average_rating.toFixed(1)} ★` : '—'}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-slate-500 text-[10px] uppercase font-bold">Depth</div>
                  <div className="text-white text-sm">{harbor.depth_meters ? `${harbor.depth_meters}m` : 'Unkn'}</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selectedHarborId && (
        <HarborDetailModal 
          harborId={selectedHarborId} 
          onClose={() => setSelectedHarborId(null)} 
        />
      )}
    </div>
  )
}
