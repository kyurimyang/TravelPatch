import { Link } from 'react-router'
import { StateCard } from '../components/StateCard'

export default function NotFound() {
  return (
    <StateCard
      kind="notfound"
      title="이 원단은 찾을 수 없어요"
      actions={
        <Link className="tp-btn-primary tp-denim" to="/">
          오늘로 가기
        </Link>
      }
    >
      <p>주소가 바뀌었거나 없는 화면이에요.</p>
    </StateCard>
  )
}
