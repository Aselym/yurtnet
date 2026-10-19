import { useEffect, useState } from 'react'

// Hash tabanli yonlendirme: sunucu yalnizca "/" servis ediyor, derin linkler
// (mailden gelen #/lisanslar?id=12 gibi) yeniden yuklemede de calisir.

export interface Route {
  page: string
  params: URLSearchParams
}

function parse(): Route {
  const h = window.location.hash.replace(/^#\/?/, '')
  const [page, qs] = h.split('?')
  return { page: page || 'genel', params: new URLSearchParams(qs || '') }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(parse)
  useEffect(() => {
    const on = () => setRoute(parse())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export function navigate(page: string, params?: Record<string, string>) {
  const qs = params ? new URLSearchParams(params).toString() : ''
  window.location.hash = `/${page}${qs ? `?${qs}` : ''}`
}
