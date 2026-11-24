import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL as string
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string

/** null when the project has no Supabase settings: the app then runs as a guest app only
 * (trips on this device), which is also how the offline demo works. */
export const supabase: SupabaseClient | null = url && anonKey ? createClient(url, anonKey) : null

/** Terms the user agreed to. Bump when a text changes, so users are asked again. */
export const TERMS_VERSION = '2026-11-25'
