// Korean particles that depend on the last syllable of a user's title ("메이지 신궁을", "하라주쿠를").
// A Hangul syllable is 0xAC00 + (lead * 21 + vowel) * 28 + tail; tail 0 = no final consonant,
// tail 8 = ㄹ (which takes 로, not 으로).

export type Josa = '을/를' | '이/가' | '은/는' | '으로/로'

const HANGUL_FIRST = 0xac00
const HANGUL_LAST = 0xd7a3
const TAIL_RIEUL = 8
// Digits as read aloud: 영 일 이 삼 사 오 육 칠 팔 구 -> their final consonant (0 = none).
const DIGIT_TAIL = [21, 8, 0, 16, 0, 0, 1, 8, 8, 0]
const UNSURE: Record<Josa, string> = { '을/를': '을(를)', '이/가': '이(가)', '은/는': '은(는)', '으로/로': '(으)로' }

/** Final consonant index of the last letter or digit, or null when it is not Hangul or a digit. */
function lastTail(word: string): number | null {
  // Skip closing quotes, brackets, punctuation and spaces: “이자카야 저녁” reads as 녁.
  const last = [...word].reverse().find((ch) => /[\p{L}\p{N}]/u.test(ch))
  if (!last) return null
  const code = last.codePointAt(0)!
  if (code >= HANGUL_FIRST && code <= HANGUL_LAST) return (code - HANGUL_FIRST) % 28
  if (/[0-9]/.test(last)) return DIGIT_TAIL[Number(last)]
  return null
}

/** Only the particle, for when the word is rendered separately (e.g. in bold). */
export function josaFor(word: string, josa: Josa): string {
  const tail = lastTail(word)
  if (tail === null) return UNSURE[josa]
  const [withTail, without] = josa.split('/')
  if (josa === '으로/로') return tail === 0 || tail === TAIL_RIEUL ? without : withTail
  return tail === 0 ? without : withTail
}

/** The word with the right particle; both forms ("을(를)") when the last letter is not Hangul. */
export function withJosa(word: string, josa: Josa): string {
  return word + josaFor(word, josa)
}
