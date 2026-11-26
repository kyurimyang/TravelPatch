import { Link } from 'react-router'
import logo from '../assets/logo.svg'
import mend from '../assets/patches/patch-mend.svg'
import stay from '../assets/patches/place-stay.svg'
import rain from '../assets/patches/hole-rain.svg'
import { GuideSteps } from '../components/GuideSteps'
import { useAuth } from '../store/auth'
import './Landing.css'

const FEATURES = [
  { icon: stay, title: '재단하기', text: '일정을 붙여넣으면 장소와 시간을 읽어 하루하루를 원단으로 정리해요.' },
  { icon: rain, title: '구멍 찾기', text: '여행 중 열차 지연, 휴무, 날씨로 구멍이 나면 영향 받는 일정까지 바로 알려 드려요.' },
  { icon: mend, title: '패치하기', text: '바뀌는 조각만 보여 드리고, 고르기 전까지 원래 일정은 그대로 남겨 둬요.' },
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
        <GuideSteps />
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
