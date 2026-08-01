import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { getBoats, getBoatInspections, getBoatInspectionStats } from '../api/boats'
import { Header } from '../components/layout/Header'
import { Card, StatCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

const TYPE_ICONS = { annual_safety:'📋', pre_trip:'🚀', post_incident:'⚠️', government:'🏛️', insurance:'🛡️', voluntary:'✅' }
const RESULT_COLORS = { passed:'green', failed:'red', conditional:'yellow', pending:'blue' }

export function InspectionCenterPage() {
  const [boats, setBoats] = useState([])
  const [selectedBoatId, setSelectedBoatId] = useState(null)
  const [inspections, setInspections] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filterResult, setFilterResult] = useState('all')

  const load = async () => {
    try { const r = await getBoats({ page:1, page_size:100 }); setBoats(r.data||[]); setLoading(false) }
    catch { setLoading(false) }
  }
  usePolling(load, 60000)

  const selectBoat = async (id) => {
    setSelectedBoatId(id)
    try {
      const [insp, st] = await Promise.all([getBoatInspections(id), getBoatInspectionStats(id)])
      setInspections(insp||[]); setStats(st)
    } catch { setInspections([]); setStats(null) }
  }

  const today = new Date()
  const filtered = filterResult==='all' ? inspections : inspections.filter(i=>i.result===filterResult)
  const selectedBoat = boats.find(b=>b.id===selectedBoatId)

  return (
    <div>
      <Header title="Inspection Center" subtitle="Safety inspection queue, history, results & compliance tracking" />

      <Card className="p-6 mb-6">
        <h3 className="text-white font-bold mb-4">Select Vessel</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {loading ? Array.from({length:6}).map((_,i)=><div key={i} className="h-14 bg-slate-700/50 rounded-xl animate-pulse"/>)
            : boats.map(b=>(
            <button key={b.id} onClick={()=>selectBoat(b.id)}
              className={`p-3 rounded-xl text-left transition-all border text-sm ${selectedBoatId===b.id?'bg-primary-600/20 border-primary-500':'bg-slate-800/50 border-slate-700/50 hover:border-primary-500/40'}`}>
              <div className="text-white font-bold truncate">🚤 {b.name}</div>
              <div className="text-slate-400 text-xs">{b.status}</div>
            </button>
          ))}
        </div>
      </Card>

      {selectedBoatId && (
        <>
          {stats && (
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
              <StatCard label="Total" value={stats.total_inspections} icon="📋" color="blue"/>
              <StatCard label="Passed" value={stats.passed} icon="✅" color="green"/>
              <StatCard label="Failed" value={stats.failed} icon="❌" color="red"/>
              <StatCard label="Overdue" value={stats.overdue} icon="⏰" color="yellow"/>
              <StatCard label="Pass Rate" value={`${stats.pass_rate}%`} icon="📊" color={stats.pass_rate>=80?'green':'red'}/>
            </div>
          )}

          <Card className="p-4 mb-4 flex flex-wrap gap-3 items-center">
            {['all','passed','failed','conditional','pending'].map(r=>(
              <button key={r} onClick={()=>setFilterResult(r)}
                className={`px-3 py-1.5 rounded-lg text-sm font-semibold capitalize transition-all ${filterResult===r?'bg-primary-600 text-white':'text-slate-400 hover:text-white bg-slate-800/50'}`}>
                {r==='all'?'All Results':r}
              </button>
            ))}
            <span className="text-slate-400 text-sm ml-auto">{filtered.length} inspections</span>
          </Card>

          <div className="space-y-4">
            {filtered.length===0 && <Card className="p-12 text-center text-slate-400">No inspections found for this vessel.</Card>}
            {filtered.map(insp=>{
              const isOverdue = insp.next_due_date && new Date(insp.next_due_date) < today
              return (
                <Card key={insp.id} className={`p-6 ${insp.result==='failed'?'border-red-500/40':''}`}>
                  <div className="flex flex-wrap items-start justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">{TYPE_ICONS[insp.inspection_type]||'📋'}</span>
                      <div>
                        <div className="text-white font-bold capitalize">{insp.inspection_type.replace(/_/g,' ')}</div>
                        <div className="text-slate-400 text-sm">{insp.inspector_name||'Inspector not recorded'}{insp.inspector_authority?` · ${insp.inspector_authority}`:''}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge color={RESULT_COLORS[insp.result]||'blue'} className="capitalize text-sm px-3">{insp.result}</Badge>
                      {isOverdue && <Badge color="red">⏰ Overdue</Badge>}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4 text-sm">
                    <div><span className="text-slate-400">Inspected:</span> <span className="text-white">{insp.inspection_date}</span></div>
                    <div><span className="text-slate-400">Next Due:</span> <span className={isOverdue?'text-red-400 font-bold':'text-white'}>{insp.next_due_date||'—'}</span></div>
                    <div><span className="text-slate-400">Certificate #:</span> <span className="text-white">{insp.certificate_number||'—'}</span></div>
                    <div><span className="text-slate-400">ID:</span> <span className="text-slate-400">#{insp.id}</span></div>
                  </div>

                  {insp.findings && (
                    <div className="bg-slate-900/50 rounded-xl p-4 mb-3">
                      <div className="text-slate-300 text-xs font-semibold mb-1">FINDINGS</div>
                      <div className="text-slate-400 text-sm">{insp.findings}</div>
                    </div>
                  )}
                  {insp.corrective_actions && (
                    <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
                      <div className="text-amber-300 text-xs font-semibold mb-1">CORRECTIVE ACTIONS REQUIRED</div>
                      <div className="text-amber-200 text-sm">{insp.corrective_actions}</div>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
