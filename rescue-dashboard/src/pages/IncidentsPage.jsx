import { useState } from 'react'
import { usePolling } from '../hooks/usePolling'
import {
  getActiveIncidents,
  getIncidentTimeline,
  transitionIncident,
  listAIIntents,
  queryAI,
} from '../api/analytics'
import { Header } from '../components/layout/Header'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { IncidentStatusBadge } from '../components/incidents/IncidentStatusBadge'
import { timeAgo } from '../utils/formatters'

// V2 core build Phase 15/16/17 (docs/INCIDENT_ENGINE.md,
// docs/AI_ARCHITECTURE.md): the incident state machine + timeline UI, and
// the Rescue AI panel — a fixed set of authorized tool-backed queries, not
// a free-text chat (no LLM credentials are configured in this
// environment; see docs/AI_ARCHITECTURE.md for why that's the honest
// choice here).

const NEXT_STEPS = {
  received: ['acknowledged', 'cancelled'],
  acknowledged: ['assessing', 'rescue_dispatched', 'cancelled'],
  assessing: ['rescue_dispatched', 'safe', 'cancelled'],
  rescue_dispatched: ['rescue_in_progress', 'cancelled'],
  rescue_in_progress: ['safe', 'cancelled'],
  safe: ['closed'],
  closed: [],
  cancelled: [],
}

function IncidentList({ incidents, selected, onSelect }) {
  if (!incidents.length) {
    return <div className="text-slate-400 text-sm text-center py-8">No open incidents.</div>
  }
  return (
    <div className="space-y-2">
      {incidents.map((i) => (
        <div
          key={i.id}
          onClick={() => onSelect(i)}
          className={`p-4 rounded-xl border cursor-pointer transition-all ${
            selected?.id === i.id ? 'border-primary-500 bg-primary-500/10' : 'border-slate-700 bg-slate-900/50 hover:border-slate-500'
          }`}
        >
          <div className="flex items-center justify-between mb-1">
            <span className="text-white font-semibold text-sm">Incident #{i.id}</span>
            <IncidentStatusBadge status={i.status} />
          </div>
          <div className="text-slate-400 text-xs">{i.incident_type || 'UNKNOWN'}</div>
          <div className="text-slate-500 text-xs mt-1">{i.created_at ? timeAgo(i.created_at) : ''}</div>
        </div>
      ))}
    </div>
  )
}

function IncidentDetail({ incident, onTransitioned }) {
  const [timeline, setTimeline] = useState([])
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const loadTimeline = async () => {
    const t = await getIncidentTimeline(incident.id)
    setTimeline(t)
  }
  usePolling(loadTimeline, 15000)

  const doTransition = async (status) => {
    setBusy(true)
    try {
      await transitionIncident(incident.id, status, reason || undefined)
      setReason('')
      await loadTimeline()
      onTransitioned()
    } catch (e) {
      alert(e.response?.data?.detail || 'Transition failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-white font-bold text-lg">Incident #{incident.id}</h3>
        <IncidentStatusBadge status={incident.status} />
      </div>

      <div className="mb-6">
        <h4 className="text-slate-300 text-sm font-semibold mb-2">Timeline</h4>
        <div className="space-y-2 border-l-2 border-slate-700 pl-4">
          {timeline.map((e, idx) => (
            <div key={idx} className="text-xs">
              <div className="text-white font-semibold">
                {e.previous_status ? `${e.previous_status} → ${e.new_status}` : e.new_status}
              </div>
              <div className="text-slate-500">{e.timestamp ? timeAgo(e.timestamp) : ''}{e.reason ? ` — ${e.reason}` : ''}</div>
            </div>
          ))}
        </div>
      </div>

      {NEXT_STEPS[incident.status]?.length > 0 && (
        <div>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Reason / notes (optional)"
            className="w-full bg-slate-900/50 border border-slate-700 rounded-xl text-white px-4 py-3 text-sm mb-3 focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
          />
          <div className="flex flex-wrap gap-2">
            {NEXT_STEPS[incident.status].map((s) => (
              <Button key={s} size="sm" variant={s === 'cancelled' ? 'ghost' : 'primary'} disabled={busy} onClick={() => doTransition(s)}>
                {s.replace('_', ' ')}
              </Button>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

function AIPanel() {
  const [intents, setIntents] = useState([])
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)

  usePolling(async () => {
    if (intents.length === 0) setIntents((await listAIIntents()).intents)
  }, 60000)

  const ask = async (intentId) => {
    setRunning(true)
    try {
      const r = await queryAI(intentId)
      setResult(r)
    } catch (e) {
      setResult({ answer: e.response?.data?.detail || 'Query failed.', data: null })
    } finally {
      setRunning(false)
    }
  }

  return (
    <Card className="p-6">
      <h3 className="text-white font-bold text-lg mb-1 flex items-center gap-2">
        <span>🤖</span> OceanGuardian AI
      </h3>
      <p className="text-slate-500 text-xs mb-4">Safety Intelligence — answers come from live authorized system data, not free-text chat.</p>

      <div className="flex flex-wrap gap-2 mb-4">
        {intents.map((i) => (
          <Button key={i.id} size="sm" variant="outline" disabled={running} onClick={() => ask(i.id)}>
            {i.label}
          </Button>
        ))}
      </div>

      {result && (
        <div className="bg-slate-900/60 border border-slate-700 rounded-xl p-4 text-sm text-slate-200 whitespace-pre-wrap">
          {result.answer}
          {result.provider && <div className="text-slate-500 text-[10px] mt-3 uppercase">via {result.provider}</div>}
        </div>
      )}

      <p className="text-slate-600 text-[10px] mt-4">
        AI is decision support, not a guarantee of safety and not a substitute for emergency services or professional rescue authority.
      </p>
    </Card>
  )
}

export function IncidentsPage() {
  const [incidents, setIncidents] = useState([])
  const [selected, setSelected] = useState(null)
  // UX audit finding (Final Release Engineering Phase L): without this,
  // the list briefly rendered "No open incidents" before the first load
  // completed — the same "absence of data shown as a clean/safe state"
  // issue flagged in the Phase G safety semantics audit, just in a
  // loading-state form rather than a missing-data form.
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const list = await getActiveIncidents()
      setIncidents(list)
      if (selected) {
        const stillOpen = list.find((i) => i.id === selected.id)
        setSelected(stillOpen || null)
      }
    } finally {
      setLoading(false)
    }
  }
  usePolling(load, 20000)

  return (
    <div>
      <Header title="Incidents" subtitle="Full lifecycle, audit trail, and AI-assisted triage" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <Card className="p-4">
            <h3 className="text-white font-bold text-sm mb-3">Open Incidents ({incidents.length})</h3>
            {loading ? (
              <div className="text-slate-400 text-xs text-center py-8">Loading…</div>
            ) : (
              <IncidentList incidents={incidents} selected={selected} onSelect={setSelected} />
            )}
          </Card>
        </div>
        <div className="lg:col-span-1">
          {selected ? <IncidentDetail incident={selected} onTransitioned={load} /> : (
            <Card className="p-6 text-slate-400 text-sm text-center">Select an incident to view its timeline.</Card>
          )}
        </div>
        <div className="lg:col-span-1">
          <AIPanel />
        </div>
      </div>
    </div>
  )
}
