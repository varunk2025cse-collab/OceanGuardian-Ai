import { Badge } from '../ui/Badge'

// Mirrors the SOSStatusBadge/PriorityBadge pattern (components/sos/) so
// incident status uses the same visual language as every other status
// indicator in the dashboard, instead of a one-off color scheme.
const MAP = {
  received:            { color: 'gray',   label: '● RECEIVED' },
  acknowledged:        { color: 'blue',   label: '◎ ACKNOWLEDGED' },
  assessing:           { color: 'yellow', label: '◐ ASSESSING' },
  rescue_dispatched:   { color: 'orange', label: '▲ DISPATCHED' },
  rescue_in_progress:  { color: 'orange', label: '▲ IN PROGRESS' },
  safe:                { color: 'green',  label: '✓ SAFE' },
  closed:              { color: 'gray',   label: '✗ CLOSED' },
  cancelled:           { color: 'gray',   label: '✗ CANCELLED' },
}

export function IncidentStatusBadge({ status }) {
  const { color, label } = MAP[status] || { color: 'gray', label: status?.toUpperCase() }
  return <Badge color={color}>{label}</Badge>
}
