import { colors } from '../../theme/colors'

export function Card({ children, className = '', gradient = false, hover = true }) {
  const baseStyle = `rounded-2xl border backdrop-blur-sm transition-all duration-300 ${
    gradient 
      ? 'border-primary-500/20 bg-gradient-to-br from-slate-800/90 to-slate-900/90' 
      : 'border-slate-700/50 bg-slate-800/80'
  } ${hover ? 'hover:border-primary-500/40 hover:shadow-xl hover:shadow-primary-500/10' : ''}`
  
  return (
    <div className={`${baseStyle} ${className}`}>
      {children}
    </div>
  )
}

export function StatCard({ label, value, trend, icon, color = 'blue', loading = false }) {
  const colorMap = {
    red: 'border-coral-500 bg-coral-500/10 text-coral-400',
    blue: 'border-primary-500 bg-primary-500/10 text-primary-400',
    green: 'border-teal-500 bg-teal-500/10 text-teal-400',
    yellow: 'border-amber-500 bg-amber-500/10 text-amber-400',
  }

  return (
    <Card className="p-6 relative overflow-hidden group">
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-slate-900/20 opacity-0 group-hover:opacity-100 transition-opacity" />
      
      <div className="relative">
        <div className={`inline-flex p-3 rounded-xl mb-4 ${colorMap[color]}`}>
          <span className="text-2xl">{icon}</span>
        </div>
        
        {loading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-slate-700 rounded w-20 mb-2"></div>
            <div className="h-4 bg-slate-700 rounded w-32"></div>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-2 mb-2">
              <div className="text-4xl font-bold text-white">{value ?? '—'}</div>
              {trend && (
                <span className={`text-sm font-medium ${trend > 0 ? 'text-coral-400' : 'text-teal-400'}`}>
                  {trend > 0 ? '↑' : '↓'} {Math.abs(trend)}%
                </span>
              )}
            </div>
            <div className="text-slate-400 text-sm font-medium">{label}</div>
          </>
        )}
      </div>
    </Card>
  )
}

export function MetricCard({ title, metrics, icon }) {
  return (
    <Card className="p-6">
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-white font-semibold text-lg">{title}</h3>
        {icon && <span className="text-2xl">{icon}</span>}
      </div>
      <div className="space-y-3">
        {metrics.map((m, i) => (
          <div key={i} className="flex justify-between items-center">
            <span className="text-slate-400 text-sm">{m.label}</span>
            <span className="text-white font-semibold">{m.value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
