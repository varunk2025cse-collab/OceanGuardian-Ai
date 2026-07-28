import api from './client'
export const login = (phone_number, password) =>
  api.post('/auth/login', { phone_number, password }).then(r => r.data)
