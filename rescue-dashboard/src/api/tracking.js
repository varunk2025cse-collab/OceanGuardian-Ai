import api from './client'

// api's instance baseURL is fixed to /api/v1 (see client.js); tracking is
// a /api/v2 resource, so override baseURL per-request rather than
// concatenating paths incorrectly.
export const getFleet = (params) =>
  api.get('/tracking/fleet', { baseURL: '/api/v2', params }).then((r) => r.data)

export const getFishermanHistory = (fishermanId, params) =>
  api.get(`/tracking/${fishermanId}/history`, { baseURL: '/api/v2', params }).then((r) => r.data)
