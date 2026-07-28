import { useState } from 'react'
import { updateSOS } from '../../api/admin'
import { SOSStatusBadge, PriorityBadge } from './SOSStatusBadge'
import { fmtCoords, fmtDateTime, timeAgo } from '../../utils/formatters'

export function SOSDetailModal({ alert, onClose, onUpdated }) {
  const [notes, setNotes] = useState(alert.rescue_notes || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const act = async (status, extra = {}) => {
    setLoading(true); setError('')
    try {
      const updated = await updateSOS(alert.id, { status, rescue_notes: notes, ...extra })
      onUpdated(updated)
      onClose()
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally { setLoading(false) }
  }

  const gmapsUrl = `https://maps.google.com/?q=${alert.latitude},${alert.longitude}`

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl w-full max-w-lg border border-slate-600 shadow-2xl"
           onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-start justify-between p-5 border-b border-slate-700">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <SOSStatusBadge status={alert.status} />
              <PriorityBadge priority={alert.priority || 'high'} />
            </div>
            <h2 className="text-white font-bold text-lg">{alert.fisherman?.full_name}</h2>
            <p className="text-slate-400 text-sm">{alert.fisherman?.boat_name || 'Unknown boat'}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-xl leading-none">✕</button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500 text-xs uppercase tracking-wide mb-1">Triggered</div>
              <div className="text-white">{fmtDateTime(alert.triggered_at)}</div>
              <div className="text-slate-400 text-xs">{timeAgo(alert.triggered_at)}</div>
            </div>
            <div>
              <div className="text-slate-500 text-xs uppercase tracking-wide mb-1">Battery</div>
              <div className="text-white">{alert.battery_level_percent != null ? `${alert.battery_level_percent}%` : '—'}</div>
            </div>
            <div className="col-span-2">
              <div className="text-slate-500 text-xs uppercase tracking-wide mb-1">Location</div>
              <div className="text-white font-mono text-sm">{fmtCoords(alert.latitude, alert.longitude)}</div>
              <a href={gmapsUrl} target="_blank" rel="noopener noreferrer"
                 className="text-blue-400 text-xs hover:underline">Open in Google Maps ↗</a>
            </div>
            {alert.fisherman?.emergency_contact_name && (
              <div className="col-span-2">
                <div className="text-slate-500 text-xs uppercase tracking-wide mb-1">Emergency Contact</div>
                <div className="text-white">{alert.fisherman.emergency_contact_name}</div>
                <div className="text-blue-300 font-mono">{alert.fisherman.emergency_contact_phone}</div>
              </div>
            )}
            {alert.message && (
              <div className="col-span-2">
                <div className="text-slate-500 text-xs uppercase tracking-wide mb-1">Message</div>
                <div className="text-yellow-300 italic">"{alert.message}"</div>
              </div>
            )}
          </div>

          <div>
            <label className="text-slate-400 text-xs uppercase tracking-wide block mb-1">Rescue Notes</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg text-white text-sm px-3 py-2 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Add notes for the rescue team…" />
          </div>
          {error && <div className="text-red-400 text-sm">{error}</div>}
        </div>

        {/* Actions */}
        {alert.status === 'active' && (
          <div className="flex gap-2 p-5 pt-0">
            <button onClick={() => act('acknowledged')} disabled={loading}
              className="flex-1 bg-yellow-600 hover:bg-yellow-500 text-white py-2 rounded-lg text-sm font-semibold disabled:opacity-50">
              Acknowledge
            </button>
            <button onClick={() => act('false_alarm')} disabled={loading}
              className="flex-1 bg-slate-600 hover:bg-slate-500 text-white py-2 rounded-lg text-sm font-semibold disabled:opacity-50">
              False Alarm
            </button>
          </div>
        )}
        {alert.status === 'acknowledged' && (
          <div className="flex gap-2 p-5 pt-0">
            <button onClick={() => act('resolved')} disabled={loading}
              className="flex-1 bg-green-600 hover:bg-green-500 text-white py-2 rounded-lg text-sm font-semibold disabled:opacity-50">
              Mark Resolved
            </button>
          </div>
        )}
        {(alert.status === 'resolved' || alert.status === 'false_alarm') && (
          <div className="p-5 pt-0">
            <button onClick={() => act(alert.status)} disabled={loading}
              className="w-full bg-slate-600 hover:bg-slate-500 text-white py-2 rounded-lg text-sm font-semibold disabled:opacity-50">
              Save Notes
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
