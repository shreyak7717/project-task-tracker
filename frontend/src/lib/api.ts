const BASE_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

const ACCESS_KEY = 'tt_access'
const REFRESH_KEY = 'tt_refresh'

export const tokenStore = {
  get access() {
    try {
      return localStorage.getItem(ACCESS_KEY)
    } catch {
      return null
    }
  },
  get refresh() {
    try {
      return localStorage.getItem(REFRESH_KEY)
    } catch {
      return null
    }
  },
  set(access: string, refresh?: string) {
    try {
      localStorage.setItem(ACCESS_KEY, access)
      if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
    } catch {
      /* ignore */
    }
  },
  clear() {
    try {
      localStorage.removeItem(ACCESS_KEY)
      localStorage.removeItem(REFRESH_KEY)
    } catch {
      /* ignore */
    }
  },
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(fn: () => void) {
  onUnauthorized = fn
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = tokenStore.refresh
  if (!refresh) return false
  const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refresh }),
  })
  if (!res.ok) return false
  const data = (await res.json()) as { access_token: string }
  tokenStore.set(data.access_token)
  return true
}

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string | number | boolean | string[] | undefined | null>
  auth?: boolean
  raw?: boolean
}

function buildUrl(path: string, params?: RequestOptions['params']) {
  const url = new URL(BASE_URL + path)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null || value === '') continue
      if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, String(v)))
      else url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function doFetch(path: string, opts: RequestOptions, retrying = false): Promise<Response> {
  const headers: Record<string, string> = {}
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.auth !== false && tokenStore.access) {
    headers.Authorization = `Bearer ${tokenStore.access}`
  }

  const res = await fetch(buildUrl(path, opts.params), {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })

  if (res.status === 401 && opts.auth !== false && !retrying) {
    const ok = await refreshAccessToken()
    if (ok) return doFetch(path, opts, true)
    tokenStore.clear()
    onUnauthorized?.()
  }
  return res
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await doFetch(path, opts)
  if (opts.raw) return res as unknown as T

  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, res.status)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export async function apiBlob(path: string, params?: RequestOptions['params']): Promise<Blob> {
  const res = await doFetch(path, { params })
  if (!res.ok) throw new ApiError(res.statusText, res.status)
  return res.blob()
}

export { BASE_URL }
