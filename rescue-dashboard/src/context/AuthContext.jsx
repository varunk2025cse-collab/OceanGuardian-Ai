import { createContext, useContext, useState } from 'react'
import { login as apiLogin } from '../api/auth'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('og_user')) } catch { return null }
  })

  const login = async (phone, password) => {
    const data = await apiLogin(phone, password)
    if (data.user.role !== 'operator')
      throw new Error('Access restricted to rescue operators only.')
    localStorage.setItem('og_token', data.access_token)
    localStorage.setItem('og_user', JSON.stringify(data.user))
    setUser(data.user)
  }

  const logout = () => {
    localStorage.removeItem('og_token')
    localStorage.removeItem('og_user')
    setUser(null)
  }

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>
}
