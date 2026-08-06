import { createContext, useContext, useState } from 'react'
import { login as apiLogin } from '../api/auth'

const AuthCtx = createContext(null)
export const useAuth = () => useContext(AuthCtx)

// Use sessionStorage instead of localStorage for tokens:
// - Tokens are bearer credentials; sessionStorage clears them when the
//   browser tab closes, reducing the window of exposure.
// - localStorage persists tokens indefinitely and is readable by any
//   script on the same origin — a stored XSS would exfiltrate them.
// - The user profile (non-sensitive) is also kept in sessionStorage for
//   consistency; the API token is the only thing that matters.
const TOKEN_KEY = 'og_token'
const USER_KEY = 'og_user'

function readSession(key) {
  try { return sessionStorage.getItem(key) } catch { return null }
}

function writeSession(key, value) {
  try { sessionStorage.setItem(key, value) } catch { /* ignore */ }
}

function removeSession(key) {
  try { sessionStorage.removeItem(key) } catch { /* ignore */ }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(readSession(USER_KEY)) } catch { return null }
  })

  const login = async (phone, password) => {
    const data = await apiLogin(phone, password)
    if (data.user.role !== 'operator')
      throw new Error('Access restricted to rescue operators only.')
    writeSession(TOKEN_KEY, data.access_token)
    writeSession(USER_KEY, JSON.stringify(data.user))
    setUser(data.user)
  }

  const logout = () => {
    removeSession(TOKEN_KEY)
    removeSession(USER_KEY)
    setUser(null)
  }

  return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>
}