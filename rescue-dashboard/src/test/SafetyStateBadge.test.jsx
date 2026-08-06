import { render, screen } from '@testing-library/react'
import { SOSStatusBadge } from '../components/sos/SOSStatusBadge'

describe('SOSStatusBadge', () => {
  it('renders critical as red', () => {
    render(<SOSStatusBadge status="active" />)
    expect(screen.getByText(/active/i)).toBeInTheDocument()
  })

  it('renders unknown status as gray fallback', () => {
    render(<SOSStatusBadge status="mystery" />)
    expect(screen.getByText(/mystery/i)).toBeInTheDocument()
  })
})
