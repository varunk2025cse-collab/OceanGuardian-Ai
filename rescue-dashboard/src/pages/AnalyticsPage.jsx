import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import { getOverview, getSosTrends, getResponseTimes, getRiskZones, getBoatHealth } from '../api/analytics'
import { Header } from '../components/layout/Header'
import { Card, StatCard, MetricCard } from '../components/ui/Card'
import { BarChart, DonutChart } from '../components/ui/SimpleChart'

// V2 core build fix (docs/V1_AUDIT.md flagged this whole page as mocked —
// ChartPlaceholder components, hardcoded "4.2 min" response time, hardcoded
// trend percentages, non-functional export buttons). Every number and
// chart on this page now comes from a real /api/v2/analytics/* call; where
// a metric genuinely isn't computed yet, it says "Not available" rather
// than showing a plausible-looking fake number.

const PERIOD_DAYS = { day: 1, week: 7, month: 30 }

export function AnalyticsPage() {
  const [period, setPeriod] = useState('week')
  const [overview, setOverview] = useState(null)
  const [sosTrends, setSosTrends] = useState(null)
  const [responseTimes, setResponseTimes] = useState(null)
  const [riskZones, setRiskZones] = useState(null)
  const [boatHealth, setBoatHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const load = async (periodOverride) => {
    try {
      const days = PERIOD_DAYS[periodOverride || period]
      const [ov, trends, rt, rz, bh] = await Promise.all([
        getOverview(),
        getSosTrends(days),
        getResponseTimes(days),
        getRiskZones(days),
        getBoatHealth(),
      ])
      setOverview(ov)
      setSosTrends(trends)
      setResponseTimes(rt)
      setRiskZones(rz)
      setBoatHealth(bh)
      setLoading(false)
      setError(false)
    } catch {
      setError(true)
      setLoading(false)
    }
  }
  usePolling(load, 60000)

  const selectPeriod = (p) => {
    setPeriod(p)
    // usePolling only re-fires on its own interval; pass the new period
    // explicitly since setPeriod's update isn't visible in this closure yet.
    load(p)
  }

  return (
    <div>
      <Header title="Analytics & Insights" subtitle="Performance metrics and trends — live backend data">
        <div className="flex gap-2 bg-slate-800/50 p-1 rounded-xl border border-slate-700">
          {['day', 'week', 'month'].map((p) => (
            <button
              key={p}
              onClick={() => selectPeriod(p)}
              className={`px-4 py-2 rounded-lg text-sm font-semibold capitalize transition-all ${
                period === p ? 'bg-primary-600 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </Header>

      {error && (
        <Card className="p-4 mb-6 border-amber-500/40 bg-amber-500/10">
          <span className="text-amber-300 text-sm">
            Analytics data unavailable — could not reach the backend. Showing the last successfully loaded values, if any.
          </span>
        </Card>
      )}

      {/* Key Metrics — all real */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard label="Total SOS Alerts" value={sosTrends?.total_alerts ?? '—'} icon="🆘" color="red" loading={loading} />
        <StatCard
          label="Avg Response Time"
          value={responseTimes?.total_resolved ? `${responseTimes.average_response_minutes.toFixed(1)} min` : 'Not available'}
          icon="⏱️"
          color="blue"
          loading={loading}
        />
        <StatCard
          label="Resolution Rate"
          value={sosTrends ? `${Math.round(sosTrends.resolution_rate * 100)}%` : '—'}
          icon="✅"
          color="green"
          loading={loading}
        />
        <StatCard label="Active Trips" value={overview?.active_trips_count ?? '—'} icon="⛵" color="yellow" loading={loading} />
      </div>

      {/* Charts Row 1 — real SOS trend + risk-zone-derived safety distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="p-6">
          <h3 className="text-white font-bold text-lg mb-4">SOS Alerts Trend</h3>
          <BarChart data={sosTrends?.trends || []} labelKey="date" valueKey="total" color="#ff1a1a" />
        </Card>
        <Card className="p-6">
          <h3 className="text-white font-bold text-lg mb-4">Fleet Safety Distribution</h3>
          <DonutChart
            segments={
              riskZones
                ? [
                    { label: 'Safe / Monitor', value: riskZones.green_risk_trips, color: '#16a34a' },
                    { label: 'Caution', value: riskZones.yellow_risk_trips, color: '#f59e0b' },
                    { label: 'High Risk', value: riskZones.red_risk_trips, color: '#ff8080' },
                    { label: 'Critical', value: riskZones.critical_risk_trips, color: '#ff1a1a' },
                  ]
                : []
            }
          />
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <Card className="p-6">
          <h3 className="text-white font-bold text-lg mb-4">Risk Zones (real SOS clustering)</h3>
          <BarChart
            data={(riskZones?.zones || []).slice(0, 6)}
            labelKey="location"
            valueKey="sos_count"
            color="#f59e0b"
          />
        </Card>
        <Card className="p-6">
          <h3 className="text-white font-bold text-lg mb-4">Boat Health</h3>
          <DonutChart
            segments={
              boatHealth
                ? [
                    { label: 'Good', value: boatHealth.good_count, color: '#16a34a' },
                    { label: 'Warning', value: boatHealth.warning_count, color: '#f59e0b' },
                    { label: 'Critical', value: boatHealth.critical_count, color: '#ff1a1a' },
                  ]
                : []
            }
          />
        </Card>
      </div>

      {/* Detailed Metrics — real */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <MetricCard
          title="Response Metrics"
          icon="⚡"
          metrics={[
            { label: 'Average Response', value: responseTimes?.total_resolved ? `${responseTimes.average_response_minutes.toFixed(1)} min` : 'Not available' },
            { label: 'Fastest Response', value: responseTimes?.total_resolved ? `${responseTimes.min_response_minutes.toFixed(1)} min` : 'Not available' },
            { label: 'Slowest Response', value: responseTimes?.total_resolved ? `${responseTimes.max_response_minutes.toFixed(1)} min` : 'Not available' },
            { label: 'Total Resolved', value: responseTimes?.total_resolved ?? 0 },
          ]}
        />

        <MetricCard
          title="Alert Breakdown"
          icon="📊"
          metrics={[
            { label: 'Resolved', value: sosTrends?.resolved_alerts ?? 0 },
            { label: 'Unresolved', value: sosTrends?.unresolved_alerts ?? 0 },
            { label: 'False Alarms', value: sosTrends?.false_alarms ?? 0 },
            { label: 'Total', value: sosTrends?.total_alerts ?? 0 },
          ]}
        />

        <MetricCard
          title="Boat Health"
          icon="🚤"
          metrics={[
            { label: 'Tracked Boats', value: boatHealth?.total_boats_tracked ?? 0 },
            { label: 'Average Score', value: boatHealth ? `${boatHealth.average_health_score}/100` : 'Not available' },
            { label: 'Overdue Maintenance', value: boatHealth?.overdue_maintenance_boats ?? 0 },
            { label: 'Active Fishermen', value: overview?.active_fishermen ?? '—' },
          ]}
        />
      </div>
    </div>
  )
}
