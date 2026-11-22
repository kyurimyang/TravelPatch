import { useState } from 'react'
import csv from '../../../eval/results/results.csv?raw'
import { StateCard } from '../components/StateCard'
import { useAuth } from '../store/auth'
import './Admin.css'

// Read-only view of the comparison experiment (eval/results/results.csv, written by
// `python -m eval.run`). Bundled at build time: re-run the experiment, rebuild, and it updates.

type Row = {
  scenario: string
  method: string
  violations: number
  preservation: number
  rc: number
  dropped: number
  ms: number
  noSolution: string
}

const METHODS: { id: string; name: string; note: string }[] = [
  { id: 'right_shift', name: 'right_shift', note: '기준선 · 뒤로 밀기' },
  { id: 'greedy', name: 'greedy', note: '기준선 · 탐욕 재배치' },
  { id: 'engine', name: 'engine', note: 'TravelPatch 패치 엔진 · 우리 방식' },
  { id: 'llm_only', name: 'llm_only', note: 'LLM 단독' },
  { id: 'llm_validated', name: 'llm_validated', note: 'LLM + 검증기' },
]
const EVENTS = ['closure', 'delay', 'extend', 'fatigue', 'weather']
const EVENT_LABEL: Record<string, string> = {
  closure: '휴무',
  delay: '지연',
  extend: '연장',
  fatigue: '체력',
  weather: '날씨',
}
// solver_ms buckets for the engine histogram (upper bounds, ms).
const BUCKETS = [100, 250, 500, 1000, 2000, Infinity]
// 1000 ms and up read as seconds so the six labels fit a 320px phone.
const fmtMs = (ms: number) => (ms >= 1000 ? `${ms / 1000}s` : `${ms}ms`)
const bucketLabel = (i: number) => (BUCKETS[i] === Infinity ? `${fmtMs(BUCKETS[i - 1])}+` : `~${fmtMs(BUCKETS[i])}`)

function parse(text: string): Row[] {
  const [, ...lines] = text.trim().split(/\r?\n/)
  return lines.map((l) => {
    const [scenario, method, violations, preservation, rc, dropped, ms, noSolution = ''] = l.split(',')
    return {
      scenario,
      method,
      violations: Number(violations),
      preservation: Number(preservation),
      rc: Number(rc),
      dropped: Number(dropped),
      ms: Number(ms),
      noSolution,
    }
  })
}

const ROWS = parse(csv)
const eventOf = (scenario: string) => scenario.split('_').slice(1).join('_')
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN)
const median = (xs: number[]) => {
  if (!xs.length) return NaN
  const s = [...xs].sort((a, b) => a - b)
  return s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2
}
const pct = (x: number) => (Number.isNaN(x) ? '–' : `${(x * 100).toFixed(1)}%`)
const num = (x: number, d = 2) => (Number.isNaN(x) ? '–' : x.toFixed(d))

function summary(method: string) {
  const rows = ROWS.filter((r) => r.method === method)
  const solved = rows.filter((r) => !r.noSolution)
  const clean = solved.filter((r) => r.violations === 0)
  return {
    n: rows.length,
    none: rows.length - solved.length,
    violationRate: solved.length ? (solved.length - clean.length) / solved.length : NaN,
    clean: clean.length,
    preservation: mean(clean.map((r) => r.preservation)),
    rc: mean(clean.map((r) => r.rc)),
    msMedian: median(rows.map((r) => r.ms)),
    msMax: Math.max(...rows.map((r) => r.ms)),
  }
}

type Filter = 'all' | 'none' | 'violations'

export default function Admin() {
  const auth = useAuth()
  const [filter, setFilter] = useState<Filter>('all')
  const [hover, setHover] = useState<number | null>(null)

  // Who may look: emails in ADMIN_EMAILS (.env). Empty list = open (local development only).
  const admins = (import.meta.env.VITE_ADMIN_EMAILS as string)
    .split(',')
    .map((e) => e.trim().toLowerCase())
    .filter(Boolean)
  const email = auth.user?.email?.toLowerCase()
  if (admins.length > 0 && (!email || !admins.includes(email))) {
    return (
      <StateCard kind="notfound" title="관리자만 볼 수 있어요">
        <p>관리자 계정으로 로그인해 주세요.</p>
      </StateCard>
    )
  }

  const methods = METHODS.filter((m) => ROWS.some((r) => r.method === m.id))
  const engine = ROWS.filter((r) => r.method === 'engine')
  const counts = BUCKETS.map(
    (_, i) => engine.filter((r) => r.ms <= BUCKETS[i] && (i === 0 || r.ms > BUCKETS[i - 1])).length,
  )
  const peak = Math.max(1, ...counts)
  const detail = engine.filter((r) =>
    filter === 'none' ? !!r.noSolution : filter === 'violations' ? r.violations > 0 : true,
  )

  return (
    <div className="admin">
      <div className="admin__head">
        <h1>평가 결과</h1>
        <p>
          시나리오 {new Set(ROWS.map((r) => r.scenario)).size}개 · 방식 {methods.length}개 비교 ·{' '}
          <code>eval/results/results.csv</code>
        </p>
        {admins.length === 0 && <p className="admin__warn">ADMIN_EMAILS가 비어 있어 누구나 볼 수 있어요(개발용).</p>}
      </div>

      <section aria-label="방식별 결과">
        <h2>복구 방식 평가 결과</h2>
        <div className="admin__scroll">
          <table className="admin__table">
            <thead>
              <tr>
                <th scope="col">방식</th>
                <th scope="col">위반율</th>
                <th scope="col">해 없음</th>
                <th scope="col">보존율*</th>
                <th scope="col">RC*</th>
                <th scope="col">solver_ms 중앙 · 최악</th>
              </tr>
            </thead>
            <tbody>
              {methods.map((m) => {
                const s = summary(m.id)
                return (
                  <tr key={m.id} className={m.id === 'engine' ? 'admin__ours' : undefined}>
                    <th scope="row">
                      <b>{m.name}</b>
                      <span>{m.note}</span>
                    </th>
                    <td>{pct(s.violationRate)}</td>
                    <td>{s.none}</td>
                    <td>{pct(s.preservation)}</td>
                    <td>{num(s.rc, 3)}</td>
                    <td>
                      {num(s.msMedian, 0)} · {num(s.msMax, 0)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="admin__note">
          * 위반 없는 일정만의 평균. 방식마다 위반 없이 푼 시나리오가 달라 직접 비교할 땐 같은 시나리오끼리 봐야
          해요(eval/results/summary.md).
        </p>
      </section>

      <section aria-label="사건 유형별 위반율">
        <h2>사건 유형별 위반율</h2>
        <div className="admin__scroll">
          <table className="admin__table">
            <thead>
              <tr>
                <th scope="col">방식</th>
                {EVENTS.map((e) => (
                  <th key={e} scope="col">
                    {EVENT_LABEL[e]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {methods.map((m) => (
                <tr key={m.id} className={m.id === 'engine' ? 'admin__ours' : undefined}>
                  <th scope="row">
                    <b>{m.name}</b>
                  </th>
                  {EVENTS.map((e) => {
                    const rows = ROWS.filter((r) => r.method === m.id && eventOf(r.scenario) === e)
                    const solved = rows.filter((r) => !r.noSolution)
                    const bad = solved.filter((r) => r.violations > 0).length
                    const none = rows.length - solved.length
                    return (
                      <td key={e}>
                        {bad}/{solved.length}
                        {none > 0 && <span className="admin__muted"> (+{none} 없음)</span>}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-label="solver_ms 분포">
        <h2>solver_ms 분포 · engine</h2>
        <div className="admin__chart" role="img" aria-label={`구간별 시나리오 수: ${counts.map((c, i) => `${bucketLabel(i)} ${c}개`).join(', ')}`}>
          {[0.5, 1].map((g) => (
            <div key={g} className="admin__grid" style={{ bottom: `${g * 100}%` }}>
              <span>{Math.round(peak * g)}</span>
            </div>
          ))}
          {counts.map((c, i) => (
            <div
              key={i}
              className="admin__col"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              tabIndex={0}
            >
              {hover === i && (
                <span className="admin__tip" role="status" style={{ bottom: `calc(${(c / peak) * 100}% + 6px)` }}>
                  {bucketLabel(i)} · 시나리오 {c}개
                </span>
              )}
              <div className="admin__bar" style={{ height: `${(c / peak) * 100}%` }} />
            </div>
          ))}
        </div>
        <div className="admin__axis">
          {counts.map((_, i) => (
            <span key={i}>{bucketLabel(i)}</span>
          ))}
        </div>
        <p className="admin__note">
          최악 {num(Math.max(...engine.map((r) => r.ms)), 0)}ms · 1초 넘는 시나리오 {engine.filter((r) => r.ms > 1000).length}개 /{' '}
          {engine.length}개
        </p>
      </section>

      <section aria-label="시나리오 상세">
        <h2>시나리오 상세 · engine</h2>
        <div className="admin__filters" role="tablist">
          {(
            [
              ['all', `전체 ${engine.length}`],
              ['none', `해 없음 ${engine.filter((r) => r.noSolution).length}`],
              ['violations', `위반 있음 ${engine.filter((r) => r.violations > 0).length}`],
            ] as const
          ).map(([id, label]) => (
            <button key={id} type="button" role="tab" aria-selected={filter === id} onClick={() => setFilter(id)}>
              {label}
            </button>
          ))}
        </div>
        <div className="admin__scroll">
          <table className="admin__table admin__table--dense">
            <thead>
              <tr>
                <th scope="col">시나리오</th>
                <th scope="col">위반</th>
                <th scope="col">보존율</th>
                <th scope="col">삭제</th>
                <th scope="col">ms</th>
              </tr>
            </thead>
            <tbody>
              {detail.map((r) => (
                <tr key={r.scenario}>
                  <th scope="row">{r.scenario}</th>
                  <td>{r.noSolution ? '해 없음' : r.violations}</td>
                  <td>{r.noSolution ? '–' : pct(r.preservation)}</td>
                  <td>{r.noSolution ? '–' : r.dropped}</td>
                  <td>{num(r.ms, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
