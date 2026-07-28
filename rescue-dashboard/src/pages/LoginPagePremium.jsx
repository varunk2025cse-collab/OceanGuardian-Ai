import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Button } from '../components/ui/Button'

export function LoginPagePremium() {
  const { login } = useAuth()
  const nav = useNavigate()
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async e => {
    e.preventDefault()
    setErr('')
    setLoading(true)
    try {
      await login(phone, password)
      nav('/')
    } catch (e) {
      setErr(e.response?.data?.detail || e.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-20 w-72 h-72 bg-primary-500/10 rounded-full blur-3xl animate-pulse-slow" />
        <div className="absolute bottom-20 right-20 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl animate-pulse-slow" style={{ animationDelay: '1s' }} />
      </div>

      <div className="w-full max-w-md relative z-10">
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500 to-teal-500 mb-4 shadow-xl shadow-primary-500/20">
            <span className="text-4xl">⚓</span>
          </div>
          <h1 className="text-white text-3xl font-bold mb-2 bg-gradient-to-r from-primary-400 to-teal-400 bg-clip-text text-transparent">
            OceanGuardian
          </h1>
          <p className="text-slate-400 text-sm">Rescue Operations Command Center</p>
        </div>

        {/* Login Form */}
        <div className="bg-slate-800/50 backdrop-blur-xl rounded-2xl p-8 border border-slate-700/50 shadow-2xl">
          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="text-slate-300 text-sm font-semibold block mb-2 flex items-center gap-2">
                <span>📱</span>
                Phone Number
              </label>
              <input
                type="tel"
                value={phone}
                onChange={e => setPhone(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl text-white px-4 py-3 text-sm focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                placeholder="+91XXXXXXXXXX"
              />
            </div>

            <div>
              <label className="text-slate-300 text-sm font-semibold block mb-2 flex items-center gap-2">
                <span>🔒</span>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-slate-900/50 border border-slate-700 rounded-xl text-white px-4 py-3 text-sm focus:outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20 transition-all"
                placeholder="Enter your password"
              />
            </div>

            {err && (
              <div className="bg-coral-500/10 border border-coral-500/30 rounded-xl px-4 py-3 flex items-start gap-3">
                <span className="text-lg">⚠️</span>
                <div className="flex-1">
                  <div className="text-coral-300 text-sm font-semibold">Login Failed</div>
                  <div className="text-coral-400/80 text-xs mt-0.5">{err}</div>
                </div>
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full"
            >
              {loading ? 'Signing in...' : 'Sign in to Dashboard'}
            </Button>

            <div className="flex items-center gap-3 pt-2">
              <div className="h-px flex-1 bg-slate-700" />
              <span className="text-slate-500 text-xs">Authorized Personnel Only</span>
              <div className="h-px flex-1 bg-slate-700" />
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center">
          <p className="text-slate-500 text-xs">
            Secured by OceanGuardian AI
          </p>
        </div>
      </div>
    </div>
  )
}
