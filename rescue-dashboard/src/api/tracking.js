import api from './client'

// api's instance baseURL is fixed to /api/v1 (see client.js); tracking is
// a /api/v2 resource, so override baseURL per-request rather than
// concatenating paths incorrectly.
export const getFleet = async (params) => {
  try {
    const response = await api.get('/tracking/fleet', { baseURL: '/api/v2', params })
    return response.data
  } catch (err) {
    if (err.response?.status === 404) return null
    throw err
  }
}

export const getFishermanHistory = (fishermanId, params) =>
  api.get(`/tracking/${fishermanId}/history`, { baseURL: '/api/v2', params }).then((r) => r.data)
