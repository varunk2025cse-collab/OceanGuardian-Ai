import { useState, useEffect } from 'react'
import { getBoat, getBoatReadiness, getBoatDocuments, getBoatCrew } from '../../api/boats'
import { BoatStatusBadge } from './BoatStatusBadge'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { fmtDateTime } from '../../utils/formatters'

export function BoatDetailModal({ boatId, onClose }) {
  const [boat, setBoat] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [documents, setDocuments] = useState([])
  const [crew, setCrew] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const [b, r, d, c] = await Promise.all([
          getBoat(boatId),
          getBoatReadiness(boatId).catch(() => null), // If not supported/implemented
          getBoatDocuments(boatId).catch(() => []),
          getBoatCrew(boatId).catch(() => []),
        ])
        setBoat(b)
        setReadiness(r)
        setDocuments(d)
        setCrew(c)
      } catch (err) {
        setError(err.response?.data?.detail || err.message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [boatId])

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
        <div className="text-white text-xl animate-pulse">Loading boat details...</div>
      </div>
    )
  }

  if (error || !boat) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50" onClick={onClose}>
        <div className="bg-slate-800 p-6 rounded-xl text-red-400 max-w-sm w-full text-center border border-red-500/30">
          <p className="mb-4">Error loading boat: {error}</p>
          <Button variant="ghost" onClick={onClose}>Close</Button>
        </div>
      </div>
    )
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'readiness', label: 'Trip Readiness' },
    { id: 'documents', label: 'Documents' },
    { id: 'crew', label: 'Crew' },
  ]

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-slate-800 rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col border border-slate-600 shadow-2xl"
           onClick={e => e.stopPropagation()}>
        
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-700">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <BoatStatusBadge status={boat.status} />
              <Badge color={boat.verification_status === 'verified' ? 'green' : 'yellow'}>
                {boat.verification_status?.toUpperCase()}
              </Badge>
            </div>
            <h2 className="text-white font-bold text-2xl">{boat.name}</h2>
            <p className="text-slate-400 text-sm font-mono mt-1">Reg: {boat.registration_number || 'N/A'}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl leading-none">✕</button>
        </div>

        {/* Navigation */}
        <div className="flex border-b border-slate-700 px-6 gap-6 overflow-x-auto">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`py-4 text-sm font-semibold whitespace-nowrap border-b-2 transition-colors ${
                activeTab === t.id ? 'border-primary-500 text-primary-400' : 'border-transparent text-slate-400 hover:text-slate-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto flex-1">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-slate-900/50 p-4 rounded-lg">
                  <div className="text-slate-500 text-xs uppercase mb-1">Vessel Class</div>
                  <div className="text-white">{boat.vessel_class || '—'}</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg">
                  <div className="text-slate-500 text-xs uppercase mb-1">Length</div>
                  <div className="text-white">{boat.length_meters ? `${boat.length_meters}m` : '—'}</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg">
                  <div className="text-slate-500 text-xs uppercase mb-1">Engine</div>
                  <div className="text-white">{boat.engine_type || '—'}</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-lg">
                  <div className="text-slate-500 text-xs uppercase mb-1">Home Harbor</div>
                  <div className="text-white">{boat.home_harbor_id ? `Harbor ID: ${boat.home_harbor_id}` : '—'}</div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'readiness' && (
            <div>
              {readiness ? (
                <div className="space-y-6">
                  <div className="flex items-center gap-4 bg-slate-900/50 p-4 rounded-xl border border-slate-700">
                    <div className={`text-4xl font-bold ${readiness.is_ready ? 'text-green-500' : 'text-red-500'}`}>
                      {readiness.safety_score}%
                    </div>
                    <div>
                      <h3 className="text-white font-bold">{readiness.is_ready ? 'Cleared for Dispatch' : 'Not Ready'}</h3>
                      <p className="text-slate-400 text-sm">Based on {readiness.evaluated_at ? fmtDateTime(readiness.evaluated_at) : 'latest'} evaluation</p>
                    </div>
                  </div>
                  {readiness.blocking_issues?.length > 0 && (
                    <div>
                      <h4 className="text-red-400 font-bold mb-2">Blocking Issues</h4>
                      <ul className="list-disc pl-5 text-slate-300 space-y-1">
                        {readiness.blocking_issues.map((issue, idx) => (
                          <li key={idx}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {readiness.warnings?.length > 0 && (
                    <div>
                      <h4 className="text-yellow-400 font-bold mb-2">Warnings</h4>
                      <ul className="list-disc pl-5 text-slate-300 space-y-1">
                        {readiness.warnings.map((warn, idx) => (
                          <li key={idx}>{warn}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-slate-400">Readiness data not available.</div>
              )}
            </div>
          )}

          {activeTab === 'documents' && (
            <div className="space-y-4">
              {documents.length === 0 ? (
                <div className="text-slate-400 text-center py-8">No documents on file.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-700 text-slate-400 text-sm">
                        <th className="py-3 pr-4 font-semibold">Type</th>
                        <th className="py-3 pr-4 font-semibold">Number</th>
                        <th className="py-3 pr-4 font-semibold">Expiry</th>
                        <th className="py-3 font-semibold">Status</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm">
                      {documents.map(doc => (
                        <tr key={doc.id} className="border-b border-slate-800">
                          <td className="py-3 pr-4 text-white">{doc.document_type}</td>
                          <td className="py-3 pr-4 text-slate-300 font-mono">{doc.document_number}</td>
                          <td className="py-3 pr-4 text-slate-300">{doc.expiry_date}</td>
                          <td className="py-3">
                            <Badge color={doc.is_verified ? 'green' : 'yellow'}>
                              {doc.is_verified ? 'VERIFIED' : 'PENDING'}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {activeTab === 'crew' && (
            <div className="space-y-4">
              {crew.length === 0 ? (
                <div className="text-slate-400 text-center py-8">No crew members assigned.</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {crew.map(member => (
                    <div key={member.id} className="bg-slate-900/50 p-4 rounded-lg border border-slate-700 flex items-center justify-between">
                      <div>
                        <div className="text-white font-semibold flex items-center gap-2">
                          {member.full_name}
                          {member.role === 'captain' && <Badge color="blue">CAPTAIN</Badge>}
                        </div>
                        <div className="text-slate-400 text-xs mt-1">{member.phone_number || 'No phone'}</div>
                      </div>
                      <Badge color={member.is_active ? 'green' : 'gray'}>
                        {member.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
