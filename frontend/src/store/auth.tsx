// Who is signed in. Login is optional (decision 2026-11-18): a guest keeps trips on this device.
// The nickname lives in `profiles` and every agreement to the terms in `consents` (migration 0003,
// decision 2026-11-19). An email sign-up sends them as metadata and the database copies them when
// the user is created (0004); a first Google login records them on the consent screen.
import type { Session, User } from '@supabase/supabase-js'
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { supabase, TERMS_VERSION } from '../lib/supabase'

export type Consent = { age14: true; terms: true; privacy: true }

type AuthStore = {
  /** false while the session or the profile is being read: do not redirect before it is known. */
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

/** What the database knows about the signed-in user, read once per sign-in.
 *  termsVersion undefined = could not be read (offline): the user is not sent to the consent
 *  screen on a guess; it is asked again on the next sign-in. */
type Profile = { userId: string; nickname: string | null; termsVersion: string | null | undefined }

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

async function readProfile(userId: string): Promise<Profile> {
  const [profile, consent] = await Promise.all([
    supabase!.from('profiles').select('nickname').eq('user_id', userId).maybeSingle(),
    supabase!
      .from('consents')
      .select('terms_version')
      .eq('user_id', userId)
      .order('agreed_at', { ascending: false })
      .limit(1)
      .maybeSingle(),
  ])
  return {
    userId,
    nickname: (profile.data?.nickname as string | undefined) ?? null,
    termsVersion: consent.error ? undefined : ((consent.data?.terms_version as string | undefined) ?? null),
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [sessionReady, setSessionReady] = useState(!supabase)
  const [profile, setProfile] = useState<Profile | null>(null)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      setSessionReady(true)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => data.subscription.unsubscribe()
  }, [])

  const user = session?.user ?? null
  const userId = user?.id ?? null

  const refreshProfile = useCallback(async () => {
    if (!supabase || !userId) return
    setProfile(await readProfile(userId))
  }, [userId])

  useEffect(() => {
    void refreshProfile()
  }, [refreshProfile])

  // The profile belongs to the user now signed in (not one read before an account switch).
  const known = profile !== null && profile.userId === userId
  const meta = (user?.user_metadata ?? {}) as { nickname?: string }

  const store: AuthStore = {
    ready: sessionReady && (!user || known),
    available: !!supabase,
    user,
    // metadata as a fallback: an email sign-up that is not confirmed yet has no profile row
    nickname: (known ? profile.nickname : null) ?? meta.nickname ?? null,
    needsConsent: !!user && known && profile.termsVersion !== undefined && profile.termsVersion !== TERMS_VERSION,
    async signIn(email, password) {
      if (!supabase) return '로그인을 쓸 수 없어요.'
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      return error ? korean(error.message) : null
    },
    async signUp(nickname, email, password, consent) {
      if (!supabase) return '가입을 쓸 수 없어요.'
      const { error } = await supabase.auth.signUp({
        email,
        password,
        // copied into profiles and consents by the database when the user is created (0004)
        options: { data: { nickname, terms_version: TERMS_VERSION, ...consent }, emailRedirectTo: `${location.origin}/` },
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
    async agree(nickname, consent) {
      if (!supabase || !userId) return '처리하지 못했어요.'
      const saved = await supabase.from('profiles').upsert({ user_id: userId, nickname })
      if (saved.error) return korean(saved.error.message)
      // a new row every time: earlier agreements stay as they were (append-only history)
      const agreed = await supabase
        .from('consents')
        .insert({ user_id: userId, terms_version: TERMS_VERSION, ...consent })
      if (agreed.error) return korean(agreed.error.message)
      await refreshProfile()
      return null
    },
    async sendPasswordReset(email) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${location.origin}/settings` })
      return error ? korean(error.message) : null
    },
    async updateProfile({ nickname }) {
      if (!supabase || !userId) return '처리하지 못했어요.'
      const { error } = await supabase.from('profiles').upsert({ user_id: userId, nickname })
      if (error) return korean(error.message)
      await refreshProfile()
      return null
    },
    async updatePassword(password) {
      if (!supabase) return '처리하지 못했어요.'
      const { error } = await supabase.auth.updateUser({ password })
      return error ? korean(error.message) : null
    },
    async signOut() {
      await supabase?.auth.signOut()
      setProfile(null)
    },
  }

  return <AuthContext.Provider value={store}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthStore {
  const store = useContext(AuthContext)
  if (!store) throw new Error('useAuth must be used inside <AuthProvider>')
  return store
}
