import api from './client'

export const getHarbors = (params) => api.get('/v2/harbor/', { params }).then(r => r.data)
export const getHarbor = (id) => api.get(`/v2/harbor/${id}`).then(r => r.data)
export const getHarborReviews = (id, params) => api.get(`/v2/harbor/${id}/reviews`, { params }).then(r => r.data)
