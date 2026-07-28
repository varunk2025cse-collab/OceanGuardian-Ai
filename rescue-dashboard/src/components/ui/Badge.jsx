export function Badge({ children, color = 'gray' }) {
  const colors = {
    red:    'bg-red-500/20 text-red-300 border border-red-500/40',
    yellow: 'bg-yellow-500/20 text-yellow-300 border border-yellow-500/40',
    green:  'bg-green-500/20 text-green-300 border border-green-500/40',
    blue:   'bg-blue-500/20 text-blue-300 border border-blue-500/40',
    gray:   'bg-slate-500/20 text-slate-300 border border-slate-500/40',
    orange: 'bg-orange-500/20 text-orange-300 border border-orange-500/40',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold ${colors[color]}`}>
      {children}
    </span>
  )
}
