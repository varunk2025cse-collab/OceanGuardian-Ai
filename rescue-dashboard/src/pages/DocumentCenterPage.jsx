import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { getBoats, getBoatDocuments, getBoatDocumentStats, getExpiringDocuments } from '../api/boats'
import { Header } from '../components/layout/Header'
import { Card, StatCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

const DOC_ICONS = { registration_certificate:'📜', fishing_license:'🎣', insurance_policy:'🛡️', inspection_certificate:'📋', seaworthiness_certificate:'⚓', crew_list:'👥', other:'📄' }
const DOC_COLORS = { registration_certificate:'blue', fishing_license:'green', insurance_policy:'yellow', inspection_certificate:'blue', seaworthiness_certificate:'green', crew_list:'blue', other:'blue' }

export function DocumentCenterPage() {
  const [boats, setBoats] = useState([])
  const [selectedBoatId, setSelectedBoatId] = useState(null)
  const [documents, setDocuments] = useState([])
  const [stats, setStats] = useState(null)
  const [expiringAll, setExpiringAll] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('documents') // 'documents' | 'expiring'
  const [filterType, setFilterType] = useState('all')

  const load = async () => {
    try {
      const [boatsRes, expiring] = await Promise.all([
        getBoats({ page:1, page_size:100 }),
        getExpiringDocuments({ within_days:30 }),
      ])
      setBoats(boatsRes.data||[])
      setExpiringAll(expiring||[])
      setLoading(false)
    } catch { setLoading(false) }
  }
  usePolling(load, 120000)

  const selectBoat = async (id) => {
    setSelectedBoatId(id); setTab('documents')
    try {
      const [docs, st] = await Promise.all([getBoatDocuments(id), getBoatDocumentStats(id)])
      setDocuments(docs||[]); setStats(st)
    } catch { setDocuments([]); setStats(null) }
  }

  const today = new Date()
  const docTypes = [...new Set(documents.map(d=>d.document_type))]
  const filtered = filterType==='all' ? documents : documents.filter(d=>d.document_type===filterType)

  const urgency = (doc) => {
    if (!doc.expiry_date) return 'no-expiry'
    const days = Math.ceil((new Date(doc.expiry_date)-today)/(1000*60*60*24))
    if (days<0) return 'expired'
    if (days<=30) return 'expiring-soon'
    return 'valid'
  }
  const urgencyColor = { expired:'red', 'expiring-soon':'yellow', valid:'green', 'no-expiry':'blue' }
  const urgencyLabel = { expired:'Expired', 'expiring-soon':'Expiring Soon', valid:'Valid', 'no-expiry':'No Expiry' }

  return (
    <div>
      <Header title="Document Center" subtitle="Boat licenses, certificates, insurance & compliance management" />

      {/* Global expiry warning banner */}
      {expiringAll.length>0 && (
        <Card className="p-4 mb-6 border-amber-500/40 bg-amber-500/10">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <div className="text-amber-300 font-bold">{expiringAll.length} document{expiringAll.length>1?'s':''} expiring fleet-wide within 30 days</div>
              <div className="text-amber-400/70 text-sm">Review expiring documents to maintain fleet compliance.</div>
            </div>
          </div>
        </Card>
      )}

      {/* Tab switcher */}
      <div className="flex gap-3 mb-6">
        {[{key:'documents',label:'📄 By Vessel'},{key:'expiring',label:`⏰ Expiring (${expiringAll.length})`}].map(t=>(
          <button key={t.key} onClick={()=>setTab(t.key)}
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${tab===t.key?'bg-primary-600 text-white':'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-700/50'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab==='expiring' && (
        <div className="space-y-3">
          {expiringAll.length===0 && <Card className="p-12 text-center text-slate-400">No documents expiring within 30 days. ✅</Card>}
          {expiringAll.map((doc,i)=>{
            const days = Math.ceil((new Date(doc.expiry_date)-today)/(1000*60*60*24))
            return (
              <Card key={i} className="p-5 flex flex-wrap items-center gap-4 border-amber-500/30">
                <span className="text-2xl">{DOC_ICONS[doc.document_type]||'📄'}</span>
                <div className="flex-1">
                  <div className="text-white font-bold capitalize">{doc.document_type?.replace(/_/g,' ')}</div>
                  <div className="text-slate-400 text-sm">Boat #{doc.boat_id}{doc.document_number?` · #${doc.document_number}`:''}</div>
                </div>
                <div className="text-right">
                  <div className="text-amber-300 font-bold">{days<0?'EXPIRED':days===0?'Expires TODAY':`${days} days left`}</div>
                  <div className="text-slate-400 text-sm">{doc.expiry_date}</div>
                </div>
                <Badge color={days<0?'red':'yellow'}>{days<0?'Expired':'Expiring'}</Badge>
              </Card>
            )
          })}
        </div>
      )}

      {tab==='documents' && (
        <>
          <Card className="p-6 mb-6">
            <h3 className="text-white font-bold mb-4">Select Vessel</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
              {loading ? Array.from({length:6}).map((_,i)=><div key={i} className="h-14 bg-slate-700/50 rounded-xl animate-pulse"/>)
                : boats.map(b=>(
                <button key={b.id} onClick={()=>selectBoat(b.id)}
                  className={`p-3 rounded-xl text-left transition-all border text-sm ${selectedBoatId===b.id?'bg-primary-600/20 border-primary-500':'bg-slate-800/50 border-slate-700/50 hover:border-primary-500/40'}`}>
                  <div className="text-white font-bold truncate">🚤 {b.name}</div>
                  <div className="text-slate-400 text-xs">{b.verification_status}</div>
                </button>
              ))}
            </div>
          </Card>

          {selectedBoatId && (
            <>
              {stats && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                  <StatCard label="Total Docs" value={stats.total||0} icon="📄" color="blue"/>
                  <StatCard label="Verified" value={stats.verified||0} icon="✅" color="green"/>
                  <StatCard label="Expired" value={stats.expired||0} icon="❌" color="red"/>
                  <StatCard label="Expiring ≤30d" value={stats.expiring_within_30_days||0} icon="⚠️" color="yellow"/>
                </div>
              )}

              <Card className="p-4 mb-4 flex flex-wrap gap-2 items-center">
                {['all',...docTypes].map(t=>(
                  <button key={t} onClick={()=>setFilterType(t)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${filterType===t?'bg-primary-600 text-white':'text-slate-400 hover:text-white bg-slate-800/50'}`}>
                    {t.replace(/_/g,' ')}
                  </button>
                ))}
              </Card>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filtered.length===0 && <div className="col-span-full text-center text-slate-400 py-12">No documents found.</div>}
                {filtered.map(doc=>{
                  const u = urgency(doc)
                  return (
                    <Card key={doc.id} className={`p-5 ${u==='expired'?'border-red-500/40':u==='expiring-soon'?'border-amber-500/40':''}`}>
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">{DOC_ICONS[doc.document_type]||'📄'}</span>
                          <div>
                            <div className="text-white font-bold text-sm capitalize">{doc.document_type?.replace(/_/g,' ')}</div>
                            <div className="text-slate-400 text-xs">{doc.issuing_authority||'Authority not recorded'}</div>
                          </div>
                        </div>
                        <Badge color={urgencyColor[u]}>{urgencyLabel[u]}</Badge>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                        <div><span className="text-slate-400">Doc #:</span> <span className="text-white">{doc.document_number||'—'}</span></div>
                        <div><span className="text-slate-400">Issued:</span> <span className="text-white">{doc.issue_date||'—'}</span></div>
                        <div><span className={u==='expired'?'text-red-400':'text-slate-400'}>Expires:</span> <span className={u==='expired'?'text-red-300 font-bold':u==='expiring-soon'?'text-amber-300 font-bold':'text-white'}>{doc.expiry_date||'No expiry'}</span></div>
                        <div><span className="text-slate-400">Verified:</span> <span className={doc.is_verified?'text-teal-400':'text-slate-400'}>{doc.is_verified?'✅ Yes':'⏳ Pending'}</span></div>
                      </div>
                      {doc.notes && <div className="text-slate-400 text-xs border-t border-slate-700/40 pt-2">{doc.notes}</div>}
                    </Card>
                  )
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
