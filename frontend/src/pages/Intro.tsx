import { Link } from 'react-router'
import logo from '../assets/logo.svg'
import mend from '../assets/patches/patch-mend.svg'
import stay from '../assets/patches/place-stay.svg'
import rain from '../assets/patches/hole-rain.svg'
import sight from '../assets/patches/place-sight.svg'
import booking from '../assets/patches/hole-booking.svg'
import delay from '../assets/patches/hole-delay.svg'
import { useAuth } from '../store/auth'
import './Landing.css'

const FEATURES = [
  { icon: stay, title: '재단하기', text: '일정을 붙여넣으면 장소와 시간을 읽어 하루하루를 원단으로 정리해요.' },
  { icon: rain, title: '구멍 찾기', text: '여행 중 열차 지연, 휴무, 날씨로 구멍이 나면 영향 받는 일정까지 바로 알려 드려요.' },
  { icon: mend, title: '패치하기', text: '바뀌는 조각만 보여 드리고, 고르기 전까지 원래 일정은 그대로 남겨 둬요.' },
]

// How to use: the order of screens the user walks through, each tied to a patch icon.
const STEPS = [
  { icon: stay, title: '일정 붙여넣기', text: '여행지·날짜·숙소를 고르고, 짜 둔 일정을 메모장이나 카톡에서 그대로 복사해 넣어요.' },
  { icon: sight, title: '재단 확인', text: '찾아 둔 장소가 맞는지, 숙소로 돌아올 시각이 맞는지만 확인해요.' },
  { icon: booking, title: '중요도 고르기', text: '조각마다 꼭 · 좋음 · 선택 중 하나를 탭해요. 꼭은 일정이 깨져도 빠지지 않아요.' },
  { icon: delay, title: '구멍 알리기', text: '여행 중 일이 생기면 지금 시각과 있는 곳을 고르고, 빠른 버튼이나 한 줄로 상황을 알려 주세요.' },
  { icon: mend, title: '패치 고르기', text: '후보를 비교하고 "왜?"를 펼쳐 이유를 확인해요. 고르기 전까지 원래 일정은 그대로예요.' },
]

// First screen while there is no trip yet. The register form itself is its own screen (/new).
export default function Intro() {
  const auth = useAuth()
  return (
    <div className="landing">
      <section className="landing__hero tp-pinked-bottom" aria-label="서비스 소개">
        <div className="landing__logo">
          <img src={logo} alt="TravelPatch" />
        </div>
        <p className="landing__tag">깨진 일정, 덧대어 고쳐요</p>
        <p className="landing__lead">
          처음부터 다시 짜지 않아요. 원래 계획에서 꼭 바꿔야 할 곳만 골라 덧대어 고치고, 왜 바꿨는지도 함께 알려 드려요.
        </p>
        <Link className="tp-btn-primary tp-denim" to="/new">
          여행 일정 등록하기
        </Link>
        {/* See a patch before typing anything: the Tokyo example day, straight to "where is the hole". */}
        <Link className="tp-btn-quiet" to="/recover" state={{ sample: true }}>
          등록 없이 예시 여행으로 먼저 보기
        </Link>
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

      <section className="landing__guide" aria-label="이렇게 써요">
        <h2>이렇게 써요</h2>
        <ol className="landing__steps">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <img src={s.icon} alt="" aria-hidden="true" />
              <div>
                <small>STEP {i + 1}</small>
                <b>{s.title}</b>
                <span>{s.text}</span>
              </div>
            </li>
          ))}
        </ol>
      </section>

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
