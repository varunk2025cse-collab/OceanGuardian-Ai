import { Badge } from '../ui/Badge'

export function TripStatusBadge({ status }) {
  const map = {
    planned:    { color: 'blue',   label: 'PLANNED' },
    active:     { color: 'green',  label: 'ACTIVE' },
    returning:  { color: 'yellow', label: 'RETURNING' },
    completed:  { color: 'gray',   label: 'COMPLETED' },
    cancelled:  { color: 'gray',   label: 'CANCELLED' },
    emergency:  { color: 'red',    label: 'EMERGENCY' },
  }
  const { color, label } = map[status] || { color: 'gray', label: status?.toUpperCase() || 'UNKNOWN' }
  return <Badge color={color}>{label}</Badge>
}
