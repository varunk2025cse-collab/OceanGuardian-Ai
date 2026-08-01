import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { Header } from '../components/layout/Header'
import { Card, StatCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import api from '../api/client'

// Pulls from family_portal_v2 notifications, which are real DB rows
const getNotifications = (params) => api.get('/v2/family/notifications', { params }).then(r => r.data)

const NOTIF_ICONS = {
  sos_alert: '🆘', sos_resolved: '✅', trip_started: '⛵', trip_completed: '🏁',
  weather_warning: '🌩️', trip_overdue: '⏰', boat_status_change: '🚤',
  maintenance_due: '🔧', document_expiring: '📄', system: '⚙️',
}
const NOTIF_COLORS = {
  sos_alert: 'red', sos_resolved: 'green', trip_started: 'blue', trip_completed: 'green',
  weather_warning: 'yellow', trip_overdue: 'red', boat_status_change: 'blue',
  maintenance_due: 'yellow', document_expiring: 'yellow', system: 'blue',
}

const PRIORITY_ORDER = { critical:0, high:1, medium:2, low:3 }

export function NotificationCenterPage() {
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filterPriority, setFilterPriority] = useState('all')
  const [filterType, setFilterType] = useState('all')

  const load = async () => {
    try {
      // family portal notifications endpoint — real DB rows from FamilyNotification model
      const data = await getNotifications({ page: 1, page_size: 100 })
      const items = Array.isArray(data) ? data : (data.data || data.notifications || [])
      setNotifications(items.sort((a,b) => (PRIORITY_ORDER[a.priority]||3) - (PRIORITY_ORDER[b.priority]||3)))
      setLoading(false); setError(null)
    } catch {
      setError('Could not load notifications — backend unreachable')
      setLoading(false)
    }
  }
  usePolling(load, 30000) // Poll every 30s for near-real-time

  const types = [...new Set(notifications.map(n => n.notification_type).filter(Boolean))]
  const filtered = notifications.filter(n =>
    (filterPriority === 'all' || n.priority === filterPriority) &&
    (filterType === 'all' || n.notification_type === filterType)
  )

  const criticalCount = notifications.filter(n => n.priority === 'critical').length
  const highCount = notifications.filter(n => n.priority === 'high').length
  const unreadCount = notifications.filter(n => !n.is_read).length
  const sosCount = notifications.filter(n => n.notification_type === 'sos_alert').length

  return (
    <div>
      <Header title="Notification Center" subtitle="Emergency alerts, weather warnings, system & family notifications — live" />

      {criticalCount > 0 && (
        <Card className="p-4 mb-6 border-red-500/60 bg-red-500/10 animate-pulse">
          <div className="flex items-center gap-3">
            <span className="text-3xl">🚨</span>
            <div>
              <div className="text-red-300 font-bold text-lg">{criticalCount} CRITICAL alert{criticalCount>1?'s':''} require immediate attention</div>
              <div className="text-red-400/70 text-sm">Review the critical notifications below immediately.</div>
            </div>
          </div>
        </Card>
      )}

      {error && (
        <Card className="p-4 mb-6 border-amber-500/40 bg-amber-500/10">
          <span className="text-amber-300 text-sm">{error}</span>
        </Card>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard label="Total" value={notifications.length} icon="🔔" color="blue" loading={loading}/>
        <StatCard label="Critical" value={criticalCount} icon="🚨" color="red" loading={loading}/>
        <StatCard label="Unread" value={unreadCount} icon="📬" color="yellow" loading={loading}/>
        <StatCard label="SOS Alerts" value={sosCount} icon="🆘" color="red" loading={loading}/>
      </div>

      {/* Filters */}
      <Card className="p-4 mb-4 flex flex-wrap gap-3 items-center">
        <div className="flex flex-wrap gap-2">
          {['all','critical','high','medium','low'].map(p=>(
            <button key={p} onClick={()=>setFilterPriority(p)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all ${filterPriority===p?'bg-primary-600 text-white':'text-slate-400 hover:text-white bg-slate-800/50'}`}>
              {p==='all'?'All Priority':p}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 ml-auto">
          <select value={filterType} onChange={e=>setFilterType(e.target.value)} className="bg-slate-900 text-white border border-slate-600 rounded-lg px-3 py-1.5 text-xs">
            <option value="all">All Types</option>
            {types.map(t=><option key={t} value={t}>{t.replace(/_/g,' ')}</option>)}
          </select>
        </div>
        <span className="text-slate-400 text-sm">{filtered.length} notifications</span>
      </Card>

      {/* Notification List */}
      <div className="space-y-3">
        {loading && Array.from({length:5}).map((_,i)=>(
          <div key={i} className="h-20 bg-slate-800/50 rounded-2xl animate-pulse border border-slate-700/50"/>
        ))}
        {!loading && filtered.length===0 && (
          <Card className="p-12 text-center">
            <div className="text-4xl mb-3">🔕</div>
            <div className="text-slate-400">No notifications match your filters.</div>
          </Card>
        )}
        {filtered.map((n, i)=>{
          const icon = NOTIF_ICONS[n.notification_type] || '🔔'
          const color = NOTIF_COLORS[n.notification_type] || 'blue'
          const isCritical = n.priority === 'critical'
          return (
            <Card key={n.id||i} className={`p-5 transition-all ${isCritical?'border-red-500/50 bg-red-500/5':!n.is_read?'border-primary-500/30':''}`}>
              <div className="flex items-start gap-4">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl flex-shrink-0 ${isCritical?'bg-red-500/20':'bg-slate-800/80'}`}>
                  {icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <span className="text-white font-bold text-sm">{n.title || n.notification_type?.replace(/_/g,' ') || 'Notification'}</span>
                    <Badge color={color} className="text-xs capitalize">{n.notification_type?.replace(/_/g,' ')}</Badge>
                    {n.priority && <Badge color={isCritical?'red':n.priority==='high'?'yellow':'blue'} className="text-xs capitalize">{n.priority}</Badge>}
                    {!n.is_read && <span className="w-2 h-2 bg-primary-400 rounded-full inline-block"/>}
                  </div>
                  <div className="text-slate-300 text-sm mb-2">{n.message || n.body || '—'}</div>
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span>📅 {n.created_at ? new Date(n.created_at).toLocaleString() : '—'}</span>
                    {n.delivery_status && <span>📡 {n.delivery_status}</span>}
                    {n.channel && <span>📢 {n.channel}</span>}
                  </div>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
