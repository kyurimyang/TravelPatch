import { useState } from 'react'
import { useNavigate } from 'react-router'
import wordmark from '../assets/wordmark.png'
import mend from '../assets/patches/patch-mend.svg'
import stay from '../assets/patches/place-stay.svg'
import rain from '../assets/patches/hole-rain.svg'
import './Landing.css'

const FEATURES = [
  { icon: stay, title: '재단하기', text: '일정을 붙여넣으면 장소와 시간을 읽어 하루하루를 원단으로 정리해요.' },
  { icon: rain, title: '구멍 찾기', text: '여행 중 열차 지연, 휴무, 날씨로 구멍이 나면 영향 받는 일정까지 바로 알려 드려요.' },
  { icon: mend, title: '패치하기', text: '바뀌는 조각만 보여 드리고, 고르기 전까지 원래 일정은 그대로 남겨 둬요.' },
]

export default function Landing() {
  const navigate = useNavigate()
  const [city, setCity] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [text, setText] = useState('')

  const canSubmit = city.trim() !== '' && start !== '' && end !== '' && start <= end && text.trim() !== ''

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    // The parser API doesn't exist yet (stage 6), so hand the raw input to the next screen via router state.
    navigate('/new/confirm', { state: { city: city.trim(), start, end, text } })
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

        <button type="submit" className="tp-btn-primary tp-denim" disabled={!canSubmit}>
          원단 재단하기
        </button>
        {/* "enter one by one" mode is not in the MVP screen list; shown disabled until decided. */}
        <button type="button" className="tp-btn-quiet" disabled>
          일정 없이 하나씩 직접 입력할게요
        </button>
      </form>

      <footer className="landing__footer">TravelPatch · 지금은 도쿄 일정부터 지원해요</footer>
    </div>
  )
}
