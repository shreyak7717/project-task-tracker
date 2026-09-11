import { createContext, use, useCallback, useEffect, useState, type ReactNode } from 'react'

import type { TokenPair, User } from '@/types'
import { api, setUnauthorizedHandler, tokenStore } from './api'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  setSession: (tokens: TokenPair) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async () => {
    if (!tokenStore.access) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(await api<User>('/api/auth/me'))
    } catch {
      tokenStore.clear()
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    void loadUser()
  }, [loadUser])

  const setSession = useCallback(
    async (tokens: TokenPair) => {
      tokenStore.set(tokens.access_token, tokens.refresh_token)
      await loadUser()
    },
    [loadUser],
  )

  const login = useCallback(
    async (email: string, password: string) => {
      const tokens = await api<TokenPair>('/api/auth/login', {
        method: 'POST',
        body: { email, password },
        auth: false,
      })
      await setSession(tokens)
    },
    [setSession],
  )

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  return (
    <AuthContext
      value={{ user, loading, login, setSession, logout, refreshUser: loadUser }}
    >
      {children}
    </AuthContext>
  )
}

export function useAuth() {
  const ctx = use(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
