import { useState, useEffect } from 'react'
import { getHarbor, getHarborReviews } from '../../api/harbors'
import { HarborFeatureBadge } from './HarborFeatureBadge'
import { Button } from '../ui/Button'
import { fmtCoords } from '../../utils/formatters'

const FEATURES = [
  'fuel_availability',
  'ice_availability',
  'medical_facility',
  'repair_facility',
  'emergency_shelter'
]

export function HarborDetailModal({ harborId, onClose }) {
  const [harbor, setHarbor] = useState(null)
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const [hData, rData] = await Promise.all([
          getHarbor(harborId),
          getHarborReviews(harborId, { limit: 5 })
        ])
        setHarbor(hData)
        setReviews(rData.reviews || [])
      } catch (err) {
        setError(err.response?.data?.detail || err.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [harborId])

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
        <div className="text-white text-xl animate-pulse">Loading harbor intelligence...</div>
      </div>
    )
  }

  if (error || !harbor) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-slate-800 p-6 rounded-xl text-red-400 max-w-sm w-full text-center border border-red-500/30">
          <p className="mb-4">Error loading harbor: {error}</p>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </div>
    )
  }

  const gmapsUrl = harbor.latitude != null && harbor.longitude != null
    ? `https://maps.google.com/?q=${harbor.latitude},${harbor.longitude}` 
    : null;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl w-full max-w-3xl max-h-[90vh] flex flex-col border border-slate-600 shadow-2xl"
           onClick={e => e.stopPropagation()}>
        
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-700 bg-slate-900/50 rounded-t-xl">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                harbor.harbor_type === 'emergency' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                harbor.harbor_type === 'major' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
                'bg-slate-500/20 text-slate-400 border border-slate-500/30'
              }`}>
                {harbor.harbor_type || 'STANDARD'}
              </span>
              <span className="text-slate-400 text-sm">{harbor.state} • {harbor.district}</span>
            </div>
            <h2 className="text-white font-bold text-2xl">{harbor.name}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">✕</button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Avg Rating</div>
              <div className="text-white font-bold text-xl text-yellow-400">
                {harbor.average_rating > 0 ? `${harbor.average_rating.toFixed(1)} ★` : 'No rating'}
              </div>
              <div className="text-slate-500 text-xs mt-1">({harbor.total_reviews} reviews)</div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Depth</div>
              <div className="text-white font-bold text-xl">{harbor.depth_meters || '--'} m</div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Operating Hours</div>
              <div className="text-white text-sm font-medium mt-2">{harbor.operating_hours || '24/7'}</div>
            </div>
            <div className="bg-slate-900/50 p-4 rounded-lg">
              <div className="text-slate-500 text-xs uppercase mb-1">Contact</div>
              <div className="text-white text-sm font-medium mt-2">{harbor.contact_number || 'N/A'}</div>
            </div>
          </div>

          <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
            <h3 className="text-white font-bold mb-3 border-b border-slate-700 pb-2 flex justify-between items-center">
              <span>Location Information</span>
              {gmapsUrl && (
                <a href={gmapsUrl} target="_blank" rel="noopener noreferrer" className="text-blue-400 text-xs hover:underline flex items-center gap-1 font-normal">
                  Open Map ↗
                </a>
              )}
            </h3>
            <div className="text-white font-mono text-sm bg-black/30 p-2 rounded w-fit">
              {harbor.latitude != null ? fmtCoords(harbor.latitude, harbor.longitude) : 'Not recorded'}
            </div>
          </div>

          <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
            <h3 className="text-white font-bold mb-3 border-b border-slate-700 pb-2">Facilities & Services</h3>
            <div className="flex flex-wrap gap-2">
              {FEATURES.map(f => (
                <HarborFeatureBadge key={f} feature={f} active={harbor[f]} />
              ))}
            </div>
          </div>

          {reviews.length > 0 && (
             <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
               <h3 className="text-white font-bold mb-3 border-b border-slate-700 pb-2">Recent Fishermen Reviews</h3>
               <div className="space-y-3">
                 {reviews.map(r => (
                   <div key={r.id} className="bg-slate-800 p-3 rounded-md text-sm border border-slate-700/50">
                     <div className="flex justify-between items-center mb-1">
                       <span className="text-yellow-400">{'★'.repeat(r.rating)}{'☆'.repeat(5-r.rating)}</span>
                       <span className="text-slate-500 text-xs">{new Date(r.created_at).toLocaleDateString()}</span>
                     </div>
                     <p className="text-slate-300 italic">"{r.review_text || 'No comment provided'}"</p>
                   </div>
                 ))}
               </div>
             </div>
          )}
        </div>
      </div>
    </div>
  )
}
