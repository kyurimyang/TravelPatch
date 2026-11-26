import { Link } from 'react-router'
import { GuideSteps } from '../components/GuideSteps'

// "/guide": how to use, for anyone at any time. The intro shows the same steps, but someone who
// is signed in or has a trip never lands there (decision 2026-11-23).
export default function Guide() {
  return (
    <div className="guide">
      <h1>이렇게 써요</h1>
      <p>처음부터 다시 짜지 않아요. 원래 계획에서 꼭 바꿔야 할 곳만 골라 덧대어 고쳐요.</p>
      <GuideSteps />
      <Link className="tp-btn-primary tp-denim" to="/new">
        새 여행 만들기
      </Link>
      <Link className="tp-btn-quiet" to="/recover" state={{ sample: true }}>
        예시 여행으로 먼저 보기
      </Link>
    </div>
  )
}
