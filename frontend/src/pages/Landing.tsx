import { useState } from 'react'
import { useNavigate } from 'react-router'
import { accessMessage } from '../api/http'
import { parseItinerary } from '../api/itineraries'
import type { PlaceOption, TravelMode } from '../api/types'
import { PlaceSearch } from '../components/PlaceSearch'
import { StitchLoader } from '../components/StitchLoader'
import { FlightFields } from '../components/FlightFields'
import { TravelModePicker } from '../components/TravelModePicker'
import { useFlowTitle } from '../layout/flowTitle'
import { tripFromDraft } from '../lib/tripFromDraft'
import { useTrip, type TripFlight } from '../store/trip'
import './Landing.css'

// Problem codes from POST /itineraries/parse -> what to tell the user.
const PARSE_PROBLEM: Record<string, string> = {
  LLM_FAILED: '일정을 읽지 못했어요. 잠시 뒤 다시 해 주세요.',
  NOTHING_FOUND: '일정을 찾지 못했어요. 한 줄에 하나씩, 시각과 장소를 적어 주세요.',
}

export default function Landing() {
  const navigate = useNavigate()
  const { setTrip } = useTrip()
  useFlowTitle('여행 일정 등록하기')
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
    } catch (e) {
      setProblem(accessMessage(e) ?? '서버에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="landing landing--form">
      <form className="landing__form" onSubmit={submit} aria-label="여행 일정 등록하기">
        <p>이미 짜 둔 일정이 있으면 그대로 붙여넣어 주세요.</p>

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
    </div>
  )
}
