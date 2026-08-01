import { useState } from 'react'
import { getTrips } from '../api/trips'
import { Header } from '../components/layout/Header'
import { usePolling } from '../hooks/usePolling'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { TripStatusBadge } from '../components/trips/TripStatusBadge'
import { TripDetailModal } from '../components/trips/TripDetailModal'
import { fmtDateTime } from '../utils/formatters'

export function TripOperationsPage() {
  const [trips, setTrips] = useState([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [selectedTripId, setSelectedTripId] = useState(null)

  const load = async () => {
    try {
      const data = await getTrips({ page_size: 100, status: statusFilter || undefined })
      setTrips(data.items || data.data || []) // handle PaginatedTrips shape
      setTotal(data.total)
      setLoading(false)
    } catch (err) {
      console.error('Failed to load trips data', err)
      setLoading(false)
    }
  }

  // Poll every 30 seconds
  usePolling(load, 30000)

  return (
    <div>
      <Header title="Trip Operations" subtitle="Enterprise fishing trip monitoring & tracking">
        <div className="flex gap-4">
          <div className="px-3 py-1.5 bg-slate-800 rounded-lg text-center">
            <div className="text-white font-bold text-lg leading-none">{total}</div>
            <div className="text-slate-400 text-[10px] uppercase font-semibold mt-1">Total Found</div>
          </div>
        </div>
      </Header>

      <div className="mb-6 flex gap-4">
        <select 
          className="bg-slate-800/80 border border-slate-700 rounded-xl text-white px-4 py-3 focus:outline-none focus:border-primary-500"
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value)
            setLoading(true)
          }}
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="planned">Planned</option>
          <option value="returning">Returning</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
          <option value="emergency">Emergency</option>
        </select>
        <Button onClick={() => { setLoading(true); load(); }}>Refresh List</Button>
      </div>

      {loading && trips.length === 0 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2, 3, 4].map(i => (
            <Card key={i} className="p-6 animate-pulse">
              <div className="flex justify-between mb-4">
                <div className="h-6 bg-slate-700 rounded w-1/3"></div>
                <div className="h-6 bg-slate-700 rounded w-1/4"></div>
              </div>
              <div className="h-16 bg-slate-700 rounded mb-4"></div>
            </Card>
          ))}
        </div>
      ) : trips.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">⛵</div>
          <div className="text-slate-400 text-lg font-medium">No trips found</div>
          <div className="text-slate-500 text-sm mt-2">
            {statusFilter ? 'Try adjusting your status filter' : 'No trips have been recorded'}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {trips.map(trip => (
            <Card 
              key={trip.id} 
              className="p-5 hover:scale-[1.01] transition-transform cursor-pointer border hover:border-primary-500/50 flex flex-col"
              onClick={() => setSelectedTripId(trip.id)}
            >
              <div className="flex items-start justify-between mb-4 border-b border-slate-700/50 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-white font-bold text-lg">Trip #{trip.id}</h3>
                    <TripStatusBadge status={trip.status} />
                  </div>
                  <div className="text-slate-400 text-sm mt-1">{trip.fisherman?.full_name}</div>
                </div>
                <div className="text-right">
                  <div className="text-slate-300 text-sm font-semibold">{trip.boat_name || 'Unknown Boat'}</div>
                  <div className="text-slate-500 text-xs font-mono">{trip.boat_registration_number}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 flex-1">
                <div>
                  <div className="text-slate-500 text-[10px] uppercase font-bold mb-1">Departure</div>
                  <div className="text-slate-300 text-sm">{fmtDateTime(trip.start_time)}</div>
                </div>
                <div>
                  <div className="text-slate-500 text-[10px] uppercase font-bold mb-1">Destination</div>
                  <div className="text-slate-300 text-sm truncate">{trip.destination || 'Open Sea'}</div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {selectedTripId && (
        <TripDetailModal 
          tripId={selectedTripId} 
          onClose={() => setSelectedTripId(null)} 
        />
      )}
    </div>
  )
}
