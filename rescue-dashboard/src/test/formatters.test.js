import { fmtDateTime, fmtCoords, timeAgo } from '../utils/formatters'

describe('formatters', () => {
  it('formats a date time string in India timezone', () => {
    const value = fmtDateTime('2026-08-05T09:00:00.000Z')
    expect(value).toContain('2026')
  })

  it('returns placeholder for falsy date input', () => {
    expect(fmtDateTime(null)).toBe('—')
    expect(fmtDateTime(undefined)).toBe('—')
  })

  it('formats coordinates when both lat and lon are present', () => {
    expect(fmtCoords(12.345678, 78.901234)).toBe('12.3457°N, 78.9012°E')
  })

  it('returns placeholder for missing coordinates', () => {
    expect(fmtCoords(null, 78.9)).toBe('—')
    expect(fmtCoords(12.3, undefined)).toBe('—')
  })

  it('formats time ago values without throwing', () => {
    expect(timeAgo(new Date(Date.now() - 5_000).toISOString())).toMatch(/s ago$/)
    expect(timeAgo(new Date(Date.now() - 65_000).toISOString())).toMatch(/m ago$/)
    expect(timeAgo(new Date(Date.now() - 3_600_000).toISOString())).toMatch(/h ago$/)
    expect(timeAgo(new Date(Date.now() - 90_000_000).toISOString())).toMatch(/d ago$/)
    expect(timeAgo(null)).toBe('—')
  })
})
