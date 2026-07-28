import { Badge } from '../ui/Badge'
export function SOSStatusBadge({ status }) {
  const map = {
    active:       { color: 'red',    label: '● ACTIVE' },
    acknowledged: { color: 'yellow', label: '◎ ACKNOWLEDGED' },
    resolved:     { color: 'green',  label: '✓ RESOLVED' },
    false_alarm:  { color: 'gray',   label: '✗ FALSE ALARM' },
  }
  const { color, label } = map[status] || { color: 'gray', label: status }
  return <Badge color={color}>{label}</Badge>
}

export function PriorityBadge({ priority }) {
  const map = {
    critical: { color: 'red',    label: '▲ CRITICAL' },
    high:     { color: 'orange', label: '▲ HIGH' },
    medium:   { color: 'blue',   label: '▲ MEDIUM' },
  }
  const { color, label } = map[priority] || { color: 'gray', label: priority }
  return <Badge color={color}>{label}</Badge>
}
