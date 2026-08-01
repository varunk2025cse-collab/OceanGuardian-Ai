export function HarborFeatureBadge({ feature, active }) {
  const map = {
    fuel_availability: { icon: '⛽', label: 'Fuel' },
    ice_availability:  { icon: '🧊', label: 'Ice' },
    medical_facility:  { icon: '🏥', label: 'Medical' },
    repair_facility:   { icon: '🔧', label: 'Repair' },
    emergency_shelter: { icon: '⛺', label: 'Shelter' },
  }
  const display = map[feature] || { icon: '🔹', label: feature }
  
  if (!active) {
    return (
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-slate-800 text-slate-500 border border-slate-700 text-xs font-medium opacity-50">
        <span>{display.icon}</span>
        <span className="line-through decoration-slate-600">{display.label}</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-primary-900/30 text-primary-300 border border-primary-500/30 text-xs font-bold shadow-sm">
      <span>{display.icon}</span>
      <span>{display.label}</span>
    </div>
  )
}
