import { Badge } from '../ui/Badge'

export function BoatStatusBadge({ status }) {
  const map = {
    registered:     { color: 'blue',   label: 'REGISTERED' },
    active:         { color: 'green',  label: 'ACTIVE' },
    inactive:       { color: 'gray',   label: 'INACTIVE' },
    maintenance:    { color: 'yellow', label: 'MAINTENANCE' },
    emergency:      { color: 'red',    label: 'EMERGENCY' },
    lost:           { color: 'red',    label: 'LOST' },
    damaged:        { color: 'orange', label: 'DAMAGED' },
    decommissioned: { color: 'gray',   label: 'DECOMMISSIONED' },
  }
  const { color, label } = map[status] || { color: 'gray', label: status?.toUpperCase() || 'UNKNOWN' }
  return <Badge color={color}>{label}</Badge>
}
