import api from './client'

export const getTrips = (params) => api.get('/v1/admin/trips', { params }).then(r => r.data)
export const getTrip = (id) => api.get(`/v1/admin/trips/${id}`).then(r => r.data)
