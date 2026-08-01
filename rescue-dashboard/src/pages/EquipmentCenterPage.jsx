import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { getBoats, getBoatEquipment, getBoatEquipmentStats } from '../api/boats'
import { Header } from '../components/layout/Header'
import { Card, StatCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'

const CAT_ICONS = { life_saving:'🛟', fire_safety:'🧯', navigation:'🧭', communication:'📡', first_aid:'🩺', fishing_gear:'🎣', engine_spare:'⚙️', other:'📦' }
const COND_COLORS = { good:'green', fair:'yellow', poor:'red', missing:'red' }

export function EquipmentCenterPage() {
  const [boats, setBoats] = useState([])
  const [selectedBoatId, setSelectedBoatId] = useState(null)
  const [equipment, setEquipment] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filterCat, setFilterCat] = useState('all')
  const [filterCond, setFilterCond] = useState('all')

  const load = async () => {
    try { const r = await getBoats({ page:1, page_size:100 }); setBoats(r.data||[]); setLoading(false) }
    catch { setLoading(false) }
  }
  usePolling(load, 60000)

  const selectBoat = async (id) => {
    setSelectedBoatId(id)
    const [eq, st] = await Promise.all([getBoatEquipment(id), getBoatEquipmentStats(id)]).catch(() => [[],null])
    setEquipment(eq||[]); setStats(st)
  }

  const today = new Date()
  const filtered = equipment.filter(i =>
    (filterCat === 'all' || i.category === filterCat) &&
    (filterCond === 'all' || i.condition === filterCond)
  )
  const categories = [...new Set(equipment.map(i => i.category))]

  return (
    <div>
      <Header title="Equipment Center" subtitle="Safety equipment inventory, compliance & maintenance tracking" />
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

      {selectedBoatId && stats && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <StatCard label="Total Items" value={stats.total_items} icon="📦" color="blue"/>
            <StatCard label="Mandatory" value={stats.mandatory_items} icon="🔴" color="red"/>
            <StatCard label="Mandatory Missing" value={stats.mandatory_missing} icon="🚨" color="red"/>
            <StatCard label="Expired" value={stats.expired_items} icon="⏰" color="yellow"/>
            <StatCard label="Compliance Score" value={`${stats.compliance_score}%`} icon="✅" color={stats.compliance_score>=80?'green':'red'}/>
          </div>

          <Card className="p-4 mb-4 flex flex-wrap gap-3 items-center">
            <select value={filterCat} onChange={e=>setFilterCat(e.target.value)} className="bg-slate-900 text-white border border-slate-600 rounded-lg px-3 py-2 text-sm">
              <option value="all">All Categories</option>
              {categories.map(c=><option key={c} value={c}>{c.replace('_',' ')}</option>)}
            </select>
            <select value={filterCond} onChange={e=>setFilterCond(e.target.value)} className="bg-slate-900 text-white border border-slate-600 rounded-lg px-3 py-2 text-sm">
              <option value="all">All Conditions</option>
              {['good','fair','poor','missing'].map(c=><option key={c} value={c}>{c}</option>)}
            </select>
            <span className="text-slate-400 text-sm">{filtered.length} items</span>
          </Card>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(item=>{
              const isExpired = item.expiry_date && new Date(item.expiry_date) < today
              return (
                <Card key={item.id} className={`p-5 ${item.is_mandatory && item.condition==='missing'?'border-red-500/60':''}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{CAT_ICONS[item.category]||'📦'}</span>
                      <div>
                        <div className="text-white font-bold text-sm">{item.item_name}</div>
                        <div className="text-slate-400 text-xs capitalize">{item.category.replace('_',' ')}</div>
                      </div>
                    </div>
                    <Badge color={COND_COLORS[item.condition]||'blue'} className="capitalize">{item.condition}</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><span className="text-slate-400">Qty:</span> <span className="text-white font-semibold">{item.quantity}</span></div>
                    <div><span className="text-slate-400">Mandatory:</span> <span className={item.is_mandatory?'text-red-400':'text-slate-300'}>{item.is_mandatory?'Yes':'No'}</span></div>
                    <div><span className="text-slate-400">Last Check:</span> <span className="text-white">{item.last_checked_at||'—'}</span></div>
                    <div><span className={isExpired?'text-red-400':'text-slate-400'}>Expiry:</span> <span className={isExpired?'text-red-300 font-bold':'text-white'}>{item.expiry_date||'—'}</span></div>
                  </div>
                  {item.notes && <div className="mt-3 text-slate-400 text-xs border-t border-slate-700/40 pt-2">{item.notes}</div>}
                </Card>
              )
            })}
            {filtered.length===0 && <div className="col-span-full text-center text-slate-400 py-12">No equipment items found.</div>}
          </div>
        </>
      )}
    </div>
  )
}
