import { useState } from 'react'
import { OP_LABEL } from '../components/DiffRow'
import { CATEGORY_LABEL, categoryIcon } from '../lib/category'
import type { SavedPatch } from '../lib/patches'
import { tripLength } from '../lib/time'
import { deviceNow, tripPhase } from '../lib/today'
import { useTrip, type Category, type Trip } from '../store/trip'
import './Patchwork.css'

// Light fabrics only: the quilt frame is indigo, so a dark weave would vanish into it.
const FABRICS = ['check', 'stripe', 'dot', 'plaid', 'butterfloral', 'hempweave', 'redfloral'] as const
// Which change a patch is "about", most telling first.
const OP_RANK = ['substitute', 'drop', 'shrink', 'move', 'extend', 'add'] as const

type Badge = { id: string; name: string; hint: string; got: (trips: Trip[], today: string) => boolean }
const allPatches = (trips: Trip[]) => trips.flatMap((t) => t.patches)
const BADGES: Badge[] = [
  { id: 'first', name: '첫 패치', hint: '처음으로 구멍을 기웠어요', got: (ts) => allPatches(ts).length > 0 },
  { id: 'survive', name: '생존 패치', hint: '늦어진 하루를 살려 냈어요', got: (ts) => allPatches(ts).some((p) => p.eventType === 'DELAY') },
  { id: 'umbrella', name: '우산 패치', hint: '비 오는 날을 기웠어요', got: (ts) => allPatches(ts).some((p) => p.eventType === 'WEATHER') },
  { id: 'swap', name: '대체 패치', hint: '닫힌 곳 대신 근처로 갔어요', got: (ts) => allPatches(ts).some((p) => p.changes.some((c) => c.op === 'substitute')) },
  { id: 'rest', name: '쉼표 패치', hint: '지친 날을 느슨하게 기웠어요', got: (ts) => allPatches(ts).some((p) => p.eventType === 'FATIGUE') },
  { id: 'stay', name: '연장 패치', hint: '좋은 곳에 더 머물렀어요', got: (ts) => allPatches(ts).some((p) => p.eventType === 'EXTEND') },
  { id: 'perfect', name: '감쪽 패치', hint: '원래 계획의 95% 이상을 지켰어요', got: (ts) => allPatches(ts).some((p) => p.preservationRate >= 0.95) },
  { id: 'quilt', name: '패치워크 완성', hint: '패치를 덧댄 여행을 끝까지 마쳤어요', got: (ts, today) => ts.some((t) => t.patches.length > 0 && tripPhase(t, today) === 'past') },
]
const BOOK: Category[] = ['sightseeing', 'meal', 'cafe', 'shopping', 'transport', 'other']

/** Share of the plan kept over the whole trip: each day counts its last patch, an unpatched day 100%. */
function keptShare(trip: Trip): number {
  if (trip.days.length === 0) return 1
  const perDay = trip.days.map((d) => {
    const ps = trip.patches.filter((p) => p.date === d.date)
    return ps.length ? ps[ps.length - 1].preservationRate : 1
  })
  return perDay.reduce((a, b) => a + b, 0) / perDay.length
}

function mainOp(p: SavedPatch): string {
  const op = OP_RANK.find((o) => p.changes.some((c) => c.op === o))
  return op ? OP_LABEL[op] : '유지'
}

const shortDate = (iso: string) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`

export default function Patchwork() {
  const { trips } = useTrip()
  const [now] = useState(deviceNow)
  const withPatches = trips.filter((t) => t.patches.length > 0)
  const finished = withPatches.filter((t) => tripPhase(t, now.date) === 'past')
  const weaving = withPatches.filter((t) => tripPhase(t, now.date) !== 'past')
  // Place book: a category counts once a piece of it was on a day that has come (not dropped).
  const collected = new Set(
    trips.flatMap((t) => t.days.filter((d) => d.date <= now.date).flatMap((d) => d.items.filter((it) => !it.dropped).map((it) => it.category))),
  )

  function quilt(t: Trip) {
    const items = t.days.flatMap((d) => d.items).slice(0, 9)
    return (
      <div className="patchwork__quilt" aria-hidden="true">
        {items.map((it, i) => (
          <div
            key={it.id}
            className={`patchwork__swatch${it.patched ? ' patchwork__swatch--patched' : ''}${it.dropped ? ' patchwork__swatch--dropped' : ''}`}
            style={{ background: `var(--tp-${FABRICS[i % FABRICS.length]})` }}
          >
            <span>
              {it.title}
              {it.patched && !it.dropped && ' · 패치'}
            </span>
          </div>
        ))}
      </div>
    )
  }

  function tripCard(t: Trip, done: boolean) {
    return (
      <article key={t.id} className={`patchwork__trip tp-fabric${done ? '' : ' patchwork__trip--weaving'}`}>
        <header>
          <b>
            {t.city} {tripLength(t.startDate, t.endDate)}
          </b>
          <span>{done ? '완성' : '짜는 중 · 여행이 끝나면 완성돼요'}</span>
        </header>
        {quilt(t)}
        <div className="patchwork__stats">
          <div>
            <span>지킨 계획</span>
            <b>{Math.floor(keptShare(t) * 100)}%</b>
          </div>
          <div>
            <span>덧댄 패치</span>
            <b>{t.patches.length}개</b>
          </div>
        </div>
        <ul className="patchwork__patches">
          {t.patches.map((p) => (
            <li key={p.id}>
              <span className="patchwork__date">{shortDate(p.date)}</span>
              <span className="patchwork__what">{p.chips.length ? p.chips.join(' · ') : '일정이 깨진 날'}</span>
              <span className="patchwork__op">{mainOp(p)}</span>
            </li>
          ))}
        </ul>
      </article>
    )
  }

  const badgeCount = BADGES.filter((b) => b.got(trips, now.date)).length

  return (
    <section className="patchwork">
      <div className="patchwork__head">
        <h1>패치 모음</h1>
        <p>여행이 끝나면 원래 계획과 덧댄 패치가 한 장의 패치워크로 남아요.</p>
      </div>

      {withPatches.length === 0 && (
        <div className="patchwork__empty tp-fabric">
          <b>아직 덧댄 패치가 없어요</b>
          <span>여행 중에 일정이 깨지면 ‘일정이 깨졌어요’에서 패치를 박음질해 보세요.</span>
        </div>
      )}
      {finished.map((t) => tripCard(t, true))}
      {weaving.map((t) => tripCard(t, false))}

      <section className="patchwork__badges" aria-label="배지 컬렉션">
        <h2>
          배지 컬렉션 <span>{badgeCount} / {BADGES.length}</span>
        </h2>
        <ul>
          {BADGES.map((b) => {
            const got = b.got(trips, now.date)
            return (
              <li key={b.id} className={got ? 'patchwork__badge' : 'patchwork__badge patchwork__badge--locked'} title={b.hint}>
                <span className="patchwork__badge-mark" aria-hidden="true" />
                <b>{got ? b.name : '아직'}</b>
                <span>{got ? b.hint : '없어요'}</span>
              </li>
            )
          })}
        </ul>
      </section>

      <section className="patchwork__book" aria-label="장소 패치 도감">
        <h2>
          장소 패치 도감 <span>{BOOK.filter((c) => collected.has(c)).length} / {BOOK.length}</span>
        </h2>
        <ul>
          {BOOK.map((c) => (
            <li key={c} className={collected.has(c) ? undefined : 'patchwork__book--locked'}>
              <img src={categoryIcon(c)} alt="" aria-hidden="true" />
              <span>{CATEGORY_LABEL[c]}</span>
            </li>
          ))}
        </ul>
      </section>
    </section>
  )
}
