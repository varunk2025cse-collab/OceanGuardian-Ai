import api from './client'

export const getBoats = (params) => api.get('/v2/boats/', { params }).then(r => r.data)
export const getBoat = (id) => api.get(`/v2/boats/${id}`).then(r => r.data)
export const getFleetSummary = () => api.get('/v2/boats/fleet/summary').then(r => r.data)
export const getBoatReadiness = (id) => api.get(`/v2/boats/${id}/readiness`).then(r => r.data)
export const getBoatDocuments = (id, params) => api.get(`/v2/boats/${id}/documents`, { params }).then(r => r.data)
export const getBoatCrew = (id, params) => api.get(`/v2/boats/${id}/crew`, { params }).then(r => r.data)
export const getBoatStatusHistory = (id) => api.get(`/v2/boats/${id}/status-history`).then(r => r.data)
export const updateBoatStatus = (id, body) => api.post(`/v2/boats/${id}/status`, body).then(r => r.data)
