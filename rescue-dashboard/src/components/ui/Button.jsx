export function Button({ children, variant = 'primary', size = 'md', icon, loading, disabled, onClick, className = '' }) {
  const variants = {
    primary: 'bg-primary-600 hover:bg-primary-700 text-white shadow-lg shadow-primary-500/20 hover:shadow-xl hover:shadow-primary-500/30',
    danger: 'bg-coral-600 hover:bg-coral-700 text-white shadow-lg shadow-coral-500/20',
    success: 'bg-teal-600 hover:bg-teal-700 text-white shadow-lg shadow-teal-500/20',
    ghost: 'bg-slate-700/50 hover:bg-slate-700 text-white border border-slate-600',
    outline: 'border-2 border-primary-500 text-primary-400 hover:bg-primary-500/10',
  }

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        ${variants[variant]} ${sizes[size]}
        rounded-xl font-semibold
        transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed
        flex items-center gap-2 justify-center
        ${className}
      `}
    >
      {loading && (
        <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      )}
      {icon && <span>{icon}</span>}
      {children}
    </button>
  )
}

export function IconButton({ icon, tooltip, onClick, variant = 'ghost', size = 'md' }) {
  const sizes = {
    sm: 'p-1.5',
    md: 'p-2',
    lg: 'p-3',
  }

  return (
    <button
      onClick={onClick}
      title={tooltip}
      className={`
        rounded-lg transition-all duration-200
        ${variant === 'ghost' ? 'hover:bg-slate-700' : 'hover:bg-primary-600'}
        ${sizes[size]}
      `}
    >
      {icon}
    </button>
  )
}
