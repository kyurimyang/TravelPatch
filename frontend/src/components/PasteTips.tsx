import './PasteTips.css'

// What to write so the parser and the engine get more to work with: a weak line next to a better one.
const TIPS = [
  { title: '시작 시각을 함께', bad: '센소지 구경', good: '09:00 센소지', why: '시각이 없으면 하루 어디에 놓을지 몰라요.' },
  { title: '끝나는 시각도', bad: '14:00 시부야', good: '14:00–16:00 시부야', why: '머무는 시간을 그대로 써요. 없으면 장소 종류로 짐작해요.' },
  { title: '예약했다면 "예약"', bad: '19:30 이자카야', good: '19:30 이자카야 예약', why: '예약한 시각은 절대 옮기지 않아요.' },
  { title: '지점까지 구체적으로', bad: '12:00 스시집', good: '12:00 스시잔마이 쓰키지점', why: '장소를 한 번에 정확히 찾아요.' },
]

// Annotated sample itinerary. Each part type also has its own underline style, so color is not the only cue.
type Mark = 'day' | 'time' | 'place' | 'flag'
const MARKS: { kind: Mark; label: string }[] = [
  { kind: 'day', label: '날짜 구분' },
  { kind: 'time', label: '시각' },
  { kind: 'place', label: '장소' },
  { kind: 'flag', label: '예약' },
]
const SAMPLE: [Mark | null, string][][] = [
  [['day', '1일차']],
  [
    ['time', '09:00–10:30'],
    [null, ' '],
    ['place', '아사쿠사 센소지'],
  ],
  [
    ['time', '12:00'],
    [null, ' 점심 - '],
    ['place', '스시잔마이 쓰키지점'],
  ],
  [
    ['time', '17:00'],
    [null, ' '],
    ['place', '시부야 스카이'],
    [null, ' '],
    ['flag', '예약'],
  ],
  [['day', '2일차']],
  [
    ['time', '10:00'],
    [null, ' '],
    ['place', '메이지 신궁'],
  ],
]

// Shown under the paste box on the register screen: closed by default so the form stays short.
export function PasteTips() {
  return (
    <details className="paste-tips">
      <summary>이렇게 적으면 더 정확해요</summary>
      <p className="paste-tips__lead">자유롭게 적어도 되지만, 네 가지만 챙기면 덜 여쭤 보고 더 잘 고쳐요.</p>
      <ul className="paste-tips__tips">
        {TIPS.map((t) => (
          <li key={t.title} className="tp-fabric">
            <b>{t.title}</b>
            <div className="paste-tips__compare">
              <span className="paste-tips__line paste-tips__line--bad">
                <em>이렇게 말고</em>
                <code>{t.bad}</code>
              </span>
              <span className="paste-tips__line paste-tips__line--good">
                <em>이렇게</em>
                <code>{t.good}</code>
              </span>
            </div>
            <span className="paste-tips__why">{t.why}</span>
          </li>
        ))}
      </ul>

      <figure className="paste-tips__sample">
        <figcaption>
          <b>이렇게 붙여넣으면 딱 좋아요</b>
          <span className="paste-tips__legend">
            {MARKS.map((m) => (
              <span key={m.kind} className={`paste-tips__mark paste-tips__mark--${m.kind}`}>
                {m.label}
              </span>
            ))}
          </span>
        </figcaption>
        <div className="paste-tips__note">
          {SAMPLE.map((line, li) => (
            <p key={li}>
              {line.map(([kind, text], si) =>
                kind ? (
                  <span key={si} className={`paste-tips__mark paste-tips__mark--${kind}`}>
                    {text}
                  </span>
                ) : (
                  text
                ),
              )}
            </p>
          ))}
        </div>
      </figure>
    </details>
  )
}
