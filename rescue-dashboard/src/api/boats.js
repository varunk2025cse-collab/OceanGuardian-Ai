import api from './client'

export const getBoats = (params) => api.get('/v2/boats/', { params }).then(r => r.data)
export const getBoat = (id) => api.get(`/v2/boats/${id}`).then(r => r.data)
export const getFleetSummary = () => api.get('/v2/boats/fleet/summary').then(r => r.data)
export const getBoatReadiness = (id) => api.get(`/v2/boats/${id}/readiness`).then(r => r.data)
export const getBoatDocuments = (id, params) => api.get(`/v2/boats/${id}/documents`, { params }).then(r => r.data)
export const getBoatDocumentStats = (id) => api.get(`/v2/boats/${id}/document-stats`).then(r => r.data)
export const getExpiringDocuments = (params) => api.get('/v2/boats/documents/expiring', { params }).then(r => r.data)
export const getBoatCrew = (id, params) => api.get(`/v2/boats/${id}/crew`, { params }).then(r => r.data)
export const getBoatCrewStats = (id) => api.get(`/v2/boats/${id}/crew-stats`).then(r => r.data)
export const getBoatEquipment = (id, params) => api.get(`/v2/boats/${id}/equipment`, { params }).then(r => r.data)
export const getBoatEquipmentStats = (id) => api.get(`/v2/boats/${id}/equipment-stats`).then(r => r.data)
export const getBoatInspections = (id, params) => api.get(`/v2/boats/${id}/inspections`, { params }).then(r => r.data)
export const getBoatInspectionStats = (id) => api.get(`/v2/boats/${id}/inspection-stats`).then(r => r.data)
export const getBoatStatusHistory = (id) => api.get(`/v2/boats/${id}/status-history`).then(r => r.data)
export const updateBoatStatus = (id, body) => api.post(`/v2/boats/${id}/status`, body).then(r => r.data)

