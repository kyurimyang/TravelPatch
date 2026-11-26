import stay from '../assets/patches/place-stay.svg'
import sight from '../assets/patches/place-sight.svg'
import booking from '../assets/patches/hole-booking.svg'
import delay from '../assets/patches/hole-delay.svg'
import mend from '../assets/patches/patch-mend.svg'
import './GuideSteps.css'

// How to use: the order of screens the user walks through, each tied to a patch icon.
// Shown on the intro (no trip yet) and on /guide (anyone, any time), so it is written once.
const STEPS = [
  { icon: stay, title: '일정 붙여넣기', text: '여행지·날짜·숙소를 고르고, 짜 둔 일정을 메모장이나 카톡에서 그대로 복사해 넣어요.' },
  { icon: sight, title: '재단 확인', text: '찾아 둔 장소가 맞는지, 숙소로 돌아올 시각이 맞는지만 확인해요. 나중에 ‘여행 고치기’에서 바꿀 수 있어요.' },
  { icon: booking, title: '중요도 고르기', text: '조각마다 꼭 · 좋음 · 선택 중 하나를 탭해요. 꼭은 일정이 깨져도 빠지지 않아요.' },
  { icon: delay, title: '구멍 알리기', text: '여행 중 일이 생기면 지금 시각과 있는 곳을 고르고, 빠른 버튼이나 한 줄로 상황을 알려 주세요.' },
  { icon: mend, title: '패치 고르기', text: '후보를 비교하고, 바뀐 조각마다 붙은 이유를 확인해요. 빠진 조각은 ‘살리기’로 되살릴 수 있어요. 고르기 전까지 원래 일정은 그대로예요.' },
]

export function GuideSteps() {
  return (
    <ol className="guide-steps">
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
  )
}
