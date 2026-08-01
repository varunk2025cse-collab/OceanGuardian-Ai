import { useState, useEffect } from 'react'
import { getTrip } from '../../api/trips'
import { TripStatusBadge } from './TripStatusBadge'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { fmtDateTime, fmtCoords } from '../../utils/formatters'

export function TripDetailModal({ tripId, onClose }) {
  const [trip, setTrip] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const t = await getTrip(tripId)
        setTrip(t)
      } catch (err) {
        setError(err.response?.data?.detail || err.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [tripId])

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
        <div className="text-white text-xl animate-pulse">Loading trip details...</div>
      </div>
    )
  }

  if (error || !trip) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-slate-800 p-6 rounded-xl text-red-400 max-w-sm w-full text-center border border-red-500/30">
          <p className="mb-4">Error loading trip: {error}</p>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </div>
    )
  }

  const gmapsUrl = trip.start_latitude != null && trip.start_longitude != null
    ? `https://maps.google.com/?q=${trip.start_latitude},${trip.start_longitude}` 
    : null;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-slate-600 shadow-2xl"
           onClick={e => e.stopPropagation()}>
        
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-700">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <TripStatusBadge status={trip.status} />
              {trip.boat_name && (
                <Badge color="blue">{trip.boat_name}</Badge>
              )}
            </div>
            <h2 className="text-white font-bold text-2xl">Trip #{trip.id}</h2>
            <p className="text-slate-400 text-sm font-mono mt-1">
              Captain: {trip.fisherman?.full_name || 'Unknown'}
            </p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">✕</button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Departure</div>
              <div className="text-white text-sm">{fmtDateTime(trip.start_time)}</div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Destination</div>
              <div className="text-white text-sm">{trip.destination || 'Open Sea'}</div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">ETA / Arrival</div>
              <div className="text-white text-sm">
                {trip.end_time ? fmtDateTime(trip.end_time) : (trip.estimated_return_at ? fmtDateTime(trip.estimated_return_at) : '—')}
              </div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Boat Reg</div>
              <div className="text-white text-sm">{trip.boat_registration_number || 'N/A'}</div>
            </div>
          </div>

          <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
            <h3 className="text-white font-bold mb-3 border-b border-slate-700 pb-2">Location Information</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-slate-500 text-xs uppercase mb-1">Start Coordinates</div>
                {trip.start_latitude != null ? (
                  <>
                    <div className="text-white font-mono text-sm">{fmtCoords(trip.start_latitude, trip.start_longitude)}</div>
                    {gmapsUrl && (
                      <a href={gmapsUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 text-xs hover:underline mt-1 inline-block">
                        View on Maps ↗
                      </a>
                    )}
                  </>
                ) : (
                  <div className="text-slate-400 text-sm">Not recorded</div>
                )}
              </div>
              <div>
                <div className="text-slate-500 text-xs uppercase mb-1">Fisherman Contact</div>
                <div className="text-white text-sm">{trip.fisherman?.phone_number || 'No phone'}</div>
              </div>
            </div>
          </div>

          {trip.notes && (
            <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
              <h3 className="text-white font-bold mb-2">Notes</h3>
              <p className="text-slate-300 text-sm">{trip.notes}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
