import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

const NAV = [
  { to: '/',          label: 'Dashboard',    icon: '📊' },
  { to: '/sos',       label: 'SOS Alerts',   icon: '🆘' },
  { to: '/map',       label: 'Live Map',     icon: '🗺️' },
  { to: '/fishermen', label: 'Fishermen',    icon: '🎣' },
  { to: '/incidents', label: 'Incidents',    icon: '🚨' },
  { to: '/analytics', label: 'Analytics',    icon: '📈' },
]

export function Sidebar({ activeSosCount }) {
  const { user, logout } = useAuth()
  return (
    <aside className="w-64 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 flex flex-col min-h-screen border-r border-slate-700/50 backdrop-blur-xl">
      <div className="px-6 py-6 border-b border-slate-700/50">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-500 to-teal-500 flex items-center justify-center text-xl">
            ⚓
          </div>
          <div>
            <div className="text-white font-bold text-lg leading-tight">OceanGuardian</div>
            <div className="text-slate-400 text-xs">Rescue Operations</div>
          </div>
        </div>
      </div>
      
      <nav className="flex-1 py-6 space-y-2 px-3">
        {NAV.map(({ to, label, icon }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-200 group relative ` +
              (isActive 
                ? 'bg-gradient-to-r from-primary-600 to-primary-700 text-white shadow-lg shadow-primary-500/20' 
                : 'text-slate-300 hover:bg-slate-700/50 hover:text-white')
            }>
            <span className="text-xl">{icon}</span>
            <span className="flex-1">{label}</span>
            {label === 'SOS Alerts' && activeSosCount > 0 && (
              <span className="bg-red-500 text-white text-xs rounded-full px-2 py-0.5 font-bold animate-pulse">
                {activeSosCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      
      <div className="px-6 py-5 border-t border-slate-700/50 bg-slate-900/50">
        <div className="mb-4">
          <div className="text-white text-sm font-semibold truncate">{user?.full_name}</div>
          <div className="text-slate-400 text-xs mt-1 truncate">{user?.phone_number}</div>
          <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-1 bg-teal-500/20 text-teal-400 rounded-lg text-xs font-semibold">
            <span className="w-1.5 h-1.5 bg-teal-400 rounded-full animate-pulse" />
            Online
          </div>
        </div>
        <button onClick={logout}
          className="w-full text-sm text-slate-300 hover:text-white py-2.5 px-4 rounded-xl border border-slate-600 hover:border-primary-500 hover:bg-slate-700/50 transition-all font-medium">
          🚪 Sign out
        </button>
      </div>
    </aside>
  )
}
