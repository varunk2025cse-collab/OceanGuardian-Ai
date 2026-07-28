export function Header({ title, subtitle, children }) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-white text-3xl font-bold mb-2 bg-gradient-to-r from-primary-400 to-teal-400 bg-clip-text text-transparent">
            {title}
          </h1>
          {subtitle && (
            <p className="text-slate-400 text-sm">{subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-3">{children}</div>
      </div>
      <div className="h-px bg-gradient-to-r from-primary-500/50 via-teal-500/50 to-transparent mt-4" />
    </div>
  )
}
