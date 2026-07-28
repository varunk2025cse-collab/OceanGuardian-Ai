/**
 * Minimal, dependency-free SVG charts. Replaces the old "Chart
 * visualization / Data analysis in progress" placeholders
 * (docs/V1_AUDIT.md flagged AnalyticsPage.jsx as fully mocked) — these
 * render whatever real data the caller passes in; if there's no data,
 * they say so explicitly rather than drawing a fake-looking chart.
 */

function EmptyState({ label = 'No data available' }) {
  return (
    <div className="h-full flex items-center justify-center text-slate-500 text-sm">
      {label}
    </div>
  )
}

export function BarChart({ data, labelKey, valueKey, color = '#0080e6', height = 220 }) {
  if (!data || data.length === 0) return <EmptyState />
  const max = Math.max(...data.map((d) => d[valueKey]), 1)
  const barWidth = 100 / data.length

  return (
    <div style={{ height }} className="w-full">
      <svg viewBox={`0 0 100 100`} preserveAspectRatio="none" className="w-full h-[calc(100%-24px)]">
        {data.map((d, i) => {
          const h = (d[valueKey] / max) * 90
          return (
            <rect
              key={i}
              x={i * barWidth + barWidth * 0.15}
              y={100 - h}
              width={barWidth * 0.7}
              height={h}
              fill={color}
              rx="1"
            >
              <title>{`${d[labelKey]}: ${d[valueKey]}`}</title>
            </rect>
          )
        })}
      </svg>
      <div className="flex justify-between mt-1 px-1">
        {data.map((d, i) => (
          <span key={i} className="text-[10px] text-slate-500 truncate" style={{ width: `${barWidth}%` }}>
            {d[labelKey]}
          </span>
        ))}
      </div>
    </div>
  )
}

export function DonutChart({ segments, height = 220 }) {
  const total = segments.reduce((s, seg) => s + seg.value, 0)
  if (!segments || total === 0) return <EmptyState />

  const radius = 40
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <div style={{ height }} className="w-full flex items-center gap-4">
      <svg viewBox="0 0 100 100" className="w-32 h-32 -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#1e293b" strokeWidth="14" />
        {segments.map((seg, i) => {
          const fraction = seg.value / total
          const dash = fraction * circumference
          const circle = (
            <circle
              key={i}
              cx="50"
              cy="50"
              r={radius}
              fill="none"
              stroke={seg.color}
              strokeWidth="14"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={-offset}
            />
          )
          offset += dash
          return circle
        })}
      </svg>
      <div className="flex-1 space-y-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="flex items-center gap-2 text-slate-300">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: seg.color }} />
              {seg.label}
            </span>
            <span className="text-slate-400 font-semibold">{seg.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
