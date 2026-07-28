import { createContext, useContext, useState, useCallback } from 'react'

const ToastContext = createContext(null)

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const show = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, type }])
    
    if (duration > 0) {
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id))
      }, duration)
    }
    
    return id
  }, [])

  const hide = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const success = useCallback((message, duration) => show(message, 'success', duration), [show])
  const error = useCallback((message, duration) => show(message, 'error', duration), [show])
  const warning = useCallback((message, duration) => show(message, 'warning', duration), [show])
  const info = useCallback((message, duration) => show(message, 'info', duration), [show])

  return (
    <ToastContext.Provider value={{ show, hide, success, error, warning, info }}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 space-y-3">
        {toasts.map(toast => (
          <Toast key={toast.id} toast={toast} onClose={() => hide(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

function Toast({ toast, onClose }) {
  const icons = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
  }

  const colors = {
    success: 'bg-teal-500/20 border-teal-500/50 text-teal-300',
    error: 'bg-red-500/20 border-red-500/50 text-red-300',
    warning: 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300',
    info: 'bg-blue-500/20 border-blue-500/50 text-blue-300',
  }

  return (
    <div className={`
      min-w-[300px] max-w-md p-4 rounded-xl border backdrop-blur-xl
      shadow-xl animate-in slide-in-from-right duration-300
      flex items-start gap-3
      ${colors[toast.type] || colors.info}
    `}>
      <span className="text-xl">{icons[toast.type] || icons.info}</span>
      <div className="flex-1 text-sm font-medium">
        {toast.message}
      </div>
      <button
        onClick={onClose}
        className="text-slate-400 hover:text-white transition-colors"
      >
        ✕
      </button>
    </div>
  )
}
