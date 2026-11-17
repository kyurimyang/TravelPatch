// Who is signed in. Login is optional (decision 2026-11-18): a guest keeps trips on this device.
// Until the profiles table exists (C2), the nickname and the terms agreement live in Supabase's
// user_metadata.
import type { Session, User } from '@supabase/supabase-js'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { supabase, TERMS_VERSION } from '../lib/supabase'

export type Consent = { age14: true; terms: true; privacy: true }

type AuthStore = {
  /** false while the saved session is being read: do not redirect before it is known. */
  ready: boolean
  /** Supabase settings exist (otherwise only guest mode). */
  available: boolean
  user: User | null
  nickname: string | null
  /** Signed in but the current terms are not agreed yet (e.g. a first Google login). */
  needsConsent: boolean
  signIn: (email: string, password: string) => Promise<string | null>
  signUp: (nickname: string, email: string, password: string, consent: Consent) => Promise<string | null>
  signInWithGoogle: () => Promise<string | null>
  agree: (nickname: string, consent: Consent) => Promise<string | null>
  sendPasswordReset: (email: string) => Promise<string | null>
  updateProfile: (fields: { nickname: string }) => Promise<string | null>
  updatePassword: (password: string) => Promise<string | null>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthStore | null>(null)

// Supabase error messages are English; the user sees Korean (CLAUDE.md 11).
function korean(message: string): string {
  const m = message.toLowerCase()
  if (m.includes('invalid login')) return '이메일이나 비밀번호가 맞지 않아요.'
  if (m.includes('already registered')) return '이미 가입한 이메일이에요. 로그인해 주세요.'
  if (m.includes('email not confirmed')) return '메일함에서 가입 확인 메일을 먼저 눌러 주세요.'
  if (m.includes('password')) return '비밀번호는 8자 이상, 영문과 숫자를 섞어 주세요.'
  if (m.includes('rate limit')) return '잠시 뒤 다시 시도해 주세요.'
  if (m.includes('provider is not enabled')) return 'Google 로그인이 아직 설정되지 않았어요.'
  return '처리하지 못했어요. 잠시 뒤 다시 시도해 주세요.'
}

const consentMeta = (nickname: string) => ({
  nickname,
  terms_version: TERMS_VERSION,
  agreed_at: new Date().toISOString(),
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(!supabase)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  const user = session?.user ?? null
  const meta = (user?.user_metadata ?? {}) as { nickname?: string; terms_version?: string }

  const store: AuthStore = {
    ready,
    available: !!supabase,
    user,
    nickname: meta.nickname ?? null,
    needsConsent: !!user && meta.terms_version !== TERMS_VERSION,
    async signIn(email, password) {
      if (!supabase) return '로그인을 쓸 수 없어요.'
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      return error ? korean(error.message) : null
    },
    async signUp(nickname, email, password) {
      if (!supabase) return '가입을 쓸 수 없어요.'
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: { data: consentMeta(nickname), emailRedirectTo: `${location.origin}/` },
      })
      return error ? korean(error.message) : null
    },
    async signInWithGoogle() {
      if (!supabase) return '로그인을 쓸 수 없어요.'
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo: `${location.origin}/` },
      })
      return error ? korean(error.message) : null
    },
    async agree(nickname) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.updateUser({ data: consentMeta(nickname) })
      return error ? korean(error.message) : null
    },
    async sendPasswordReset(email) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${location.origin}/settings` })
      return error ? korean(error.message) : null
    },
    async updateProfile({ nickname }) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.updateUser({ data: { nickname } })
      return error ? korean(error.message) : null
    },
    async updatePassword(password) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.updateUser({ password })
      return error ? korean(error.message) : null
    },
    async signOut() {
      await supabase?.auth.signOut()
    },
  }

  return <AuthContext.Provider value={store}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthStore {
  const store = useContext(AuthContext)
  if (!store) throw new Error('useAuth must be used inside <AuthProvider>')
  return store
}
