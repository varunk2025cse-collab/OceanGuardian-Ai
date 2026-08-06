import axios from 'axios'
const api = axios.create({ baseURL: '/api/v1', timeout: 15000 })
api.interceptors.request.use(cfg => {
  const token = sessionStorage.getItem('og_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})
api.interceptors.response.use(r => r, err => {
  if (err.response?.status === 401) {
    sessionStorage.removeItem('og_token')
    sessionStorage.removeItem('og_user')
    window.location.href = '/login'
  }
  return Promise.reject(err)
})
export default api