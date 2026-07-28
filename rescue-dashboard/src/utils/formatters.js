export function timeAgo(dateStr) {
  if (!dateStr) return '—'
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`
  return `${Math.floor(diff/86400)}d ago`
}
export function fmtCoords(lat, lon) {
  if (!lat || !lon) return '—'
  return `${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E`
}
export function fmtDateTime(d) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: true })
}
