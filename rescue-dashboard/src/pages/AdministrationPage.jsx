import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { Header } from '../components/layout/Header'
import { Card, StatCard, MetricCard } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import api from '../api/client'

const getAdminStats = () => api.get('/admin/stats').then(r => r.data)
const getSystemHealth = () => api.get('/health').then(r => r.data).catch(() => ({ status: 'unknown' }))
const getFishermen = (p) => api.get('/admin/fishermen', { params: p }).then(r => r.data)

export function AdministrationPage() {
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview') // overview | users | health
  const [userSearch, setUserSearch] = useState('')

  const load = async () => {
    try {
      const [s, h, u] = await Promise.all([
        getAdminStats(),
        getSystemHealth(),
        getFishermen({ page: 1, page_size: 50 }),
      ])
      setStats(s)
      setHealth(h)
      setUsers(Array.isArray(u) ? u : (u.data || []))
      setLoading(false)
      setError(null)
    } catch {
      setError('Could not load admin data')
      setLoading(false)
    }
  }
  usePolling(load, 60000)

  const filteredUsers = users.filter(u =>
    (u.full_name || '').toLowerCase().includes(userSearch.toLowerCase()) ||
    (u.phone_number || '').includes(userSearch)
  )

  const tabs = [
    { key: 'overview', label: '📊 Overview', },
    { key: 'users', label: `👥 Users (${users.length})` },
    { key: 'health', label: '❤️ System Health' },
  ]

  return (
    <div>
      <Header title="Administration" subtitle="Users, system health, audit logs, permissions & API monitoring" />

      {error && (
        <Card className="p-4 mb-6 border-amber-500/40 bg-amber-500/10">
          <span className="text-amber-300 text-sm">{error}</span>
        </Card>
      )}

      {/* Tab bar */}
      <div className="flex gap-3 mb-6">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${activeTab === t.key ? 'bg-primary-600 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-white border border-slate-700/50'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW TAB ─────────────────────────────── */}
      {activeTab === 'overview' && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard label="Total Users" value={stats?.total_fishermen ?? '—'} icon="👥" color="blue" loading={loading} />
            <StatCard label="Active SOS" value={stats?.active_sos ?? '—'} icon="🆘" color="red" loading={loading} />
            <StatCard label="Active Trips" value={stats?.active_trips ?? '—'} icon="⛵" color="green" loading={loading} />
            <StatCard label="Total Boats" value={stats?.total_boats ?? '—'} icon="🚤" color="yellow" loading={loading} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <MetricCard title="Platform Metrics" icon="📊" metrics={[
              { label: 'Total Fishermen', value: stats?.total_fishermen ?? '—' },
              { label: 'Total Trips', value: stats?.total_trips ?? '—' },
              { label: 'Total SOS', value: stats?.total_sos ?? '—' },
              { label: 'Resolved SOS', value: stats?.resolved_sos ?? '—' },
            ]} />
            <MetricCard title="Fleet Health" icon="🚤" metrics={[
              { label: 'Total Boats', value: stats?.total_boats ?? '—' },
              { label: 'Active Trips', value: stats?.active_trips ?? '—' },
              { label: 'Active SOS', value: stats?.active_sos ?? '—' },
              { label: 'Unresolved SOS', value: (stats?.total_sos ?? 0) - (stats?.resolved_sos ?? 0) },
            ]} />
            <MetricCard title="API Status" icon="🌐" metrics={[
              { label: 'Backend', value: health?.status === 'ok' ? '✅ Online' : '⚠️ Degraded' },
              { label: 'Database', value: health?.database === 'ok' ? '✅ OK' : '⚠️ Check' },
              { label: 'Weather API', value: health?.weather_api ?? '—' },
              { label: 'Version', value: health?.version ?? '—' },
            ]} />
          </div>

          {/* Role breakdown */}
          {stats?.by_role && (
            <Card className="p-6">
              <h3 className="text-white font-bold text-lg mb-4">User Role Distribution</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                {Object.entries(stats.by_role).map(([role, count]) => (
                  <div key={role} className="bg-slate-900/50 rounded-xl p-4 text-center border border-slate-700/30">
                    <div className="text-white font-bold text-2xl">{count}</div>
                    <div className="text-slate-400 text-sm capitalize">{role}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {/* ── USERS TAB ─────────────────────────────────── */}
      {activeTab === 'users' && (
        <>
          <Card className="p-4 mb-4">
            <input type="text" placeholder="🔍 Search users by name or phone..."
              value={userSearch} onChange={e => setUserSearch(e.target.value)}
              className="w-full bg-slate-900/50 text-white border border-slate-600 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-primary-500 transition-colors" />
          </Card>
          <Card className="overflow-hidden">
            <div className="p-6 border-b border-slate-700/50">
              <h3 className="text-white font-bold text-lg">Registered Users — {filteredUsers.length} shown</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800/50 border-b border-slate-700/50">
                    {['User', 'Phone', 'Role', 'Status', 'Registered'].map(h => (
                      <th key={h} className="text-left text-slate-300 text-xs font-semibold uppercase tracking-wider px-6 py-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loading && Array.from({length:5}).map((_,i) => (
                    <tr key={i}><td colSpan={5} className="px-6 py-4"><div className="h-4 bg-slate-700/50 rounded animate-pulse"/></td></tr>
                  ))}
                  {!loading && filteredUsers.length === 0 && (
                    <tr><td colSpan={5} className="px-6 py-12 text-center text-slate-400">No users found.</td></tr>
                  )}
                  {filteredUsers.map(u => (
                    <tr key={u.id} className="border-b border-slate-700/30 hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-500 to-teal-500 flex items-center justify-center text-sm font-bold text-white">
                            {(u.full_name||'?')[0].toUpperCase()}
                          </div>
                          <div>
                            <div className="text-white font-semibold text-sm">{u.full_name || '—'}</div>
                            <div className="text-slate-500 text-xs">#{u.id}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-slate-300 text-sm">{u.phone_number || '—'}</td>
                      <td className="px-6 py-4"><Badge color={u.role==='operator'?'yellow':u.role==='admin'?'red':'blue'} className="capitalize">{u.role}</Badge></td>
                      <td className="px-6 py-4"><Badge color={u.is_active!==false?'green':'red'}>{u.is_active!==false?'Active':'Inactive'}</Badge></td>
                      <td className="px-6 py-4 text-slate-400 text-sm">{u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}

      {/* ── HEALTH TAB ─────────────────────────────────── */}
      {activeTab === 'health' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
            <Card className={`p-6 text-center ${health?.status === 'ok' ? 'border-teal-500/40' : 'border-amber-500/40'}`}>
              <div className="text-5xl mb-3">{health?.status === 'ok' ? '✅' : '⚠️'}</div>
              <div className="text-white font-bold text-lg">Backend API</div>
              <div className={`text-sm font-semibold mt-1 ${health?.status === 'ok' ? 'text-teal-400' : 'text-amber-400'}`}>
                {health?.status?.toUpperCase() || 'UNKNOWN'}
              </div>
            </Card>
            <Card className={`p-6 text-center ${health?.database === 'ok' ? 'border-teal-500/40' : 'border-amber-500/40'}`}>
              <div className="text-5xl mb-3">{health?.database === 'ok' ? '🟢' : '🟡'}</div>
              <div className="text-white font-bold text-lg">Database</div>
              <div className={`text-sm font-semibold mt-1 ${health?.database === 'ok' ? 'text-teal-400' : 'text-amber-400'}`}>
                {health?.database?.toUpperCase() || 'UNKNOWN'}
              </div>
            </Card>
            <Card className="p-6 text-center">
              <div className="text-5xl mb-3">📡</div>
              <div className="text-white font-bold text-lg">Platform Version</div>
              <div className="text-primary-400 text-sm font-semibold mt-1">{health?.version || 'v0.5.0'}</div>
            </Card>
          </div>

          <Card className="p-6">
            <h3 className="text-white font-bold text-lg mb-4">Live Health Snapshot</h3>
            <div className="space-y-3">
              {health ? Object.entries(health).map(([key, val]) => (
                <div key={key} className="flex justify-between items-center py-2 border-b border-slate-700/30">
                  <span className="text-slate-400 text-sm capitalize">{key.replace(/_/g,' ')}</span>
                  <span className={`text-sm font-semibold ${String(val)==='ok'||String(val)==='true'?'text-teal-400':String(val)==='error'||String(val)==='false'?'text-red-400':'text-white'}`}>
                    {String(val)}
                  </span>
                </div>
              )) : (
                <div className="text-slate-400 text-center py-6">Loading health data...</div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
