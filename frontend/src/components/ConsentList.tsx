import { Link } from 'react-router'

export type ConsentState = { age14: boolean; terms: boolean; privacy: boolean }
export const NO_CONSENT: ConsentState = { age14: false, terms: false, privacy: false }
export const allAgreed = (c: ConsentState) => c.age14 && c.terms && c.privacy

const ITEMS: { key: keyof ConsentState; label: string; doc?: string }[] = [
  { key: 'age14', label: '만 14세 이상이에요' },
  { key: 'terms', label: '이용약관', doc: 'terms' },
  { key: 'privacy', label: '개인정보 수집·이용', doc: 'privacy' },
]

// Sign-up terms: one "agree to all" plus the required items, each with its full text one tap away.
// No location item: GPS is out of the MVP (decision 2026-11-17).
export function ConsentList({ value, onChange }: { value: ConsentState; onChange: (c: ConsentState) => void }) {
  const all = allAgreed(value)
  return (
    <fieldset className="account__consent">
      <legend>약관 동의</legend>
      <label className="account__consent-all">
        <input
          type="checkbox"
          checked={all}
          onChange={() => onChange({ age14: !all, terms: !all, privacy: !all })}
        />
        전체 동의
      </label>
      {ITEMS.map((it) => (
        <div key={it.key} className="account__consent-row">
          <label>
            <input
              type="checkbox"
              checked={value[it.key]}
              onChange={(e) => onChange({ ...value, [it.key]: e.target.checked })}
            />
            <span className="account__required">[필수]</span> {it.label}
          </label>
          {it.doc && (
            <Link to={`/legal/${it.doc}`} target="_blank">
              보기
            </Link>
          )}
        </div>
      ))}
    </fieldset>
  )
}
