import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { parseItinerary } from '../api/itineraries'
import type { PlaceOption, TravelMode } from '../api/types'
import wordmark from '../assets/wordmark.png'
import mend from '../assets/patches/patch-mend.svg'
import stay from '../assets/patches/place-stay.svg'
import rain from '../assets/patches/hole-rain.svg'
import { PlaceSearch } from '../components/PlaceSearch'
import { StitchLoader } from '../components/StitchLoader'
import { FlightFields } from '../components/FlightFields'
import { TravelModePicker } from '../components/TravelModePicker'
import { tripFromDraft } from '../lib/tripFromDraft'
import { useAuth } from '../store/auth'
import { useTrip, type TripFlight } from '../store/trip'
import './Landing.css'

// Problem codes from POST /itineraries/parse -> what to tell the user.
const PARSE_PROBLEM: Record<string, string> = {
  LLM_FAILED: '일정을 읽지 못했어요. 잠시 뒤 다시 해 주세요.',
  NOTHING_FOUND: '일정을 찾지 못했어요. 한 줄에 하나씩, 시각과 장소를 적어 주세요.',
}

const FEATURES = [
  { icon: stay, title: '재단하기', text: '일정을 붙여넣으면 장소와 시간을 읽어 하루하루를 원단으로 정리해요.' },
  { icon: rain, title: '구멍 찾기', text: '여행 중 열차 지연, 휴무, 날씨로 구멍이 나면 영향 받는 일정까지 바로 알려 드려요.' },
  { icon: mend, title: '패치하기', text: '바뀌는 조각만 보여 드리고, 고르기 전까지 원래 일정은 그대로 남겨 둬요.' },
]

export default function Landing() {
  const navigate = useNavigate()
  const { setTrip } = useTrip()
  const auth = useAuth()
  const [city, setCity] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  // The Google option is shown while registering only; the trip keeps the typed words + place_id.
  const [hotel, setHotel] = useState<{ option: PlaceOption; title: string } | null>(null)
  const [travelMode, setTravelMode] = useState<TravelMode>('transit')
  const [arrival, setArrival] = useState<TripFlight | null>(null)
  const [departure, setDeparture] = useState<TripFlight | null>(null)
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  const canSubmit =
    city.trim() !== '' && start !== '' && end !== '' && start <= end && hotel !== null && text.trim() !== '' && !busy

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit || !hotel) return
    setBusy(true)
    setProblem(null)
    try {
      const res = await parseItinerary(text)
      if (res.status !== 'ok' || !res.draft) {
        setProblem(PARSE_PROBLEM[res.problem?.code ?? ''] ?? PARSE_PROBLEM.LLM_FAILED)
        return
      }
      const meta = {
        city: city.trim(),
        startDate: start,
        endDate: end,
        hotel: { title: hotel.title, placeId: hotel.option.place_id },
        travelMode,
        arrival,
        departure,
      }
      setTrip(tripFromDraft(res.draft, meta))
      navigate('/new/confirm')
    } catch {
      setProblem('서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="landing">
      <section className="landing__hero tp-pinked-bottom" aria-label="서비스 소개">
        <div className="landing__logo">
          <img src={wordmark} alt="TravelPatch" />
        </div>
        <p className="landing__tag">깨진 일정, 덧대어 고쳐요</p>
        <p className="landing__lead">
          처음부터 다시 짜지 않아요. 원래 계획에서 꼭 바꿔야 할 곳만 골라 덧대어 고치고, 왜 바꿨는지도 함께 알려 드려요.
        </p>
        <a className="tp-btn-primary tp-denim" href="#register">
          여행 일정 등록하기
        </a>
      </section>

      <section className="landing__features" aria-label="이렇게 도와드려요">
        <h2>이렇게 도와드려요</h2>
        {FEATURES.map((f) => (
          <div className="landing__feature" key={f.title}>
            <img src={f.icon} alt="" aria-hidden="true" />
            <div>
              <b>{f.title}</b>
              <span>{f.text}</span>
            </div>
          </div>
        ))}
      </section>

      <form id="register" className="landing__form" onSubmit={submit} aria-label="여행 일정 등록하기">
        <div>
          <h2>여행 일정 등록하기</h2>
          <p>이미 짜 둔 일정이 있으면 그대로 붙여넣어 주세요.</p>
        </div>

        <div className="landing__field">
          <label htmlFor="reg-city">여행지</label>
          <input id="reg-city" type="text" placeholder="예: 도쿄" value={city} onChange={(e) => setCity(e.target.value)} />
        </div>

        <div className="landing__dates">
          <div className="landing__field">
            <label htmlFor="reg-start">가는 날</label>
            <input id="reg-start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="landing__field">
            <label htmlFor="reg-end">오는 날</label>
            <input id="reg-end" type="date" min={start} value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
        </div>

        <div className="landing__field">
          <label htmlFor="reg-hotel">숙소</label>
          <PlaceSearch
            inputId="reg-hotel"
            city={city}
            placeholder="예: 신주쿠 워싱턴 호텔"
            picked={hotel?.option ?? null}
            onPick={(option, title) => setHotel({ option, title })}
          />
          <span>하루가 숙소에서 시작하고, 일정이 깨져도 숙소로 돌아올 시간은 지켜요.</span>
        </div>

        <div className="landing__field">
          <span className="landing__label">주로 어떻게 다니세요?</span>
          <TravelModePicker name="reg-mode" value={travelMode} onChange={setTravelMode} />
          <span>장소 사이 이동 시간을 이 수단으로 계산해요. 나중에 바꿀 수 있어요.</span>
        </div>

        <div className="landing__field">
          <span className="landing__label">항공편 (선택)</span>
          <FlightFields direction="arrival" city={city} value={arrival} onChange={setArrival} />
          <FlightFields direction="departure" city={city} value={departure} onChange={setDeparture} />
        </div>

        <div className="landing__field">
          <label htmlFor="reg-paste">일정 붙여넣기</label>
          <textarea
            id="reg-paste"
            rows={7}
            aria-describedby="reg-paste-hint"
            placeholder={'예)\n1일차\n09:00 아사쿠사 센소지\n12:00 점심 - 스시\n15:00 시부야 스카이'}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <span id="reg-paste-hint">
            메모장, 카톡, 엑셀 어디서 복사해도 괜찮아요. 정리한 뒤 장소가 맞는지 한 번 확인해 드릴게요.
          </span>
        </div>

        {busy && (
          <StitchLoader
            size="inline"
            steps={['붙여넣은 일정을 읽고 있어요', '날짜와 시간을 나누고 있어요', '조각으로 재단하고 있어요']}
          />
        )}
        {problem && (
          <p className="landing__problem" role="alert">
            {problem}
          </p>
        )}
        <button type="submit" className="tp-btn-primary tp-denim" disabled={!canSubmit}>
          {busy ? '재단하고 있어요…' : '원단 재단하기'}
        </button>
        {/* "enter one by one" mode is not in the MVP screen list; shown disabled until decided. */}
        <button type="button" className="tp-btn-quiet" disabled>
          일정 없이 하나씩 직접 입력할게요
        </button>
      </form>

      <p className="landing__account">
        {auth.user ? (
          <>{auth.nickname ?? auth.user.email}님으로 로그인했어요</>
        ) : (
          <>
            여행을 다른 기기에서도 보려면 <Link to="/login">로그인</Link>
          </>
        )}
      </p>

      <footer className="landing__footer">
        TravelPatch · 한 여행에 한 도시씩 지원해요 · <Link to="/legal/terms">약관</Link> ·{' '}
        <Link to="/legal/privacy">개인정보 처리방침</Link>
      </footer>
    </div>
  )
}
