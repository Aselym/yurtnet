import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

/** deps degistikce yeniden yukler; eski istegin cevabi yenisini ezmez. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const seq = useRef(0)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    fn().then(
      (d) => { if (id === seq.current) { setData(d); setLoading(false) } },
      (e: unknown) => {
        if (id === seq.current) {
          setError(e instanceof Error ? e.message : 'Veri yüklenemedi.')
          setLoading(false)
        }
      },
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, loading, error, reload }
}

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function useLocal<T>(key: string, initial: T): [T, (v: T) => void] {
  const [v, setV] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })
  const set = useCallback((nv: T) => {
    setV(nv)
    try { localStorage.setItem(key, JSON.stringify(nv)) } catch { /* yok say */ }
  }, [key])
  return [v, set]
}

export function useOutside(ref: React.RefObject<HTMLElement | null>, onOut: () => void, active = true) {
  useEffect(() => {
    if (!active) return
    const h = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOut()
    }
    const k = (e: KeyboardEvent) => { if (e.key === 'Escape') onOut() }
    document.addEventListener('mousedown', h)
    document.addEventListener('keydown', k)
    return () => {
      document.removeEventListener('mousedown', h)
      document.removeEventListener('keydown', k)
    }
  }, [ref, onOut, active])
}
