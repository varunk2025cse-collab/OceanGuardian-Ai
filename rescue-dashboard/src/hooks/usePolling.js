import { useEffect, useRef } from 'react'
export function usePolling(fn, intervalMs = 30000) {
  const ref = useRef(fn)
  ref.current = fn
  useEffect(() => {
    ref.current()
    const id = setInterval(() => ref.current(), intervalMs)
    return () => clearInterval(id)
  }, [intervalMs])
}
