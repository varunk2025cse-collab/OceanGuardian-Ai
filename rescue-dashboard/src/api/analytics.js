import api from './client'

// /api/v2/analytics/* — see backend/app/routers/v2/analytics.py. Same
// baseURL-override pattern as api/tracking.js (the shared `api` instance
// is pinned to /api/v1).
const v2 = (path, params) => api.get(path, { baseURL: '/api/v2', params }).then((r) => r.data)

export const getOverview = () => v2('/analytics/overview')
export const getSosTrends = (days = 7) => v2('/analytics/sos-trends', { days })
export const getResponseTimes = (days = 30) => v2('/analytics/response-times', { days })
export const getActiveBoats = () => v2('/analytics/active-boats')
export const getRiskZones = (days = 7) => v2('/analytics/risk-zones', { days })
export const getBoatHealth = () => v2('/analytics/boat-health')

// /api/v2/safety/* — see backend/app/routers/v2/safety.py
export const getFleetSafetySummary = () => v2('/safety/fleet/summary')

// /api/v2/incidents/* — see backend/app/routers/v2/incidents.py
export const getActiveIncidents = () => v2('/incidents/active')
export const getIncident = (id) => v2(`/incidents/${id}`)
export const getIncidentTimeline = (id) => v2(`/incidents/${id}/timeline`)
export const transitionIncident = (id, status, reason) =>
  api.post(`/incidents/${id}/transition`, { status, reason }, { baseURL: '/api/v2' }).then((r) => r.data)

// /api/v2/ai/* — see backend/app/routers/v2/ai.py
export const listAIIntents = () => v2('/ai/intents')
export const queryAI = (intent, fishermanId, incidentId) =>
  api
    .post('/ai/query', { intent, fisherman_id: fishermanId, incident_id: incidentId }, { baseURL: '/api/v2' })
    .then((r) => r.data)
