import api from './client'
export const getStats = () => api.get('/admin/stats').then(r => r.data)
export const getSOS = (params) => api.get('/admin/sos', { params }).then(r => r.data)
export const getSOSById = (id) => api.get(`/admin/sos/${id}`).then(r => r.data)
export const updateSOS = (id, body) => api.patch(`/admin/sos/${id}/status`, body).then(r => r.data)
export const getFishermen = (params) => api.get('/admin/fishermen', { params }).then(r => r.data)
export const getFishermanLocations = (id) => api.get(`/admin/fishermen/${id}/locations`).then(r => r.data)
export const getWeather = () => api.get('/weather/active').then(r => r.data)
export const getHarbors = () => api.get('/harbors/').then(r => r.data)
