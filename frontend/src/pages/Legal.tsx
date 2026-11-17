import { Link, useParams } from 'react-router'
import { TERMS_VERSION } from '../lib/supabase'
import NotFound from './NotFound'
import './Account.css'

// Draft texts. What the system really does is written in; legal facts only the operator can state
// (who runs it, how long things are kept, contact) are left as "[작성 필요]" — never made up.
type Section = { title: string; body: string[] }
const DOCS: Record<string, { title: string; sections: Section[] }> = {
  terms: {
    title: '이용약관',
    sections: [
      { title: '1. 목적', body: ['이 약관은 [운영자 이름 · 작성 필요](이하 ‘TravelPatch’)가 제공하는 여행 일정 복구 서비스의 이용 조건을 정해요.'] },
      {
        title: '2. 서비스 내용',
        body: [
          '등록한 여행 일정을 정리하고, 여행 중 일정이 깨지면 원래 일정에 대한 최소한의 변경(패치)을 계산해 보여 줘요.',
          '패치는 제안이에요. 실제 예약·운영 여부는 현장에서 확인해 주세요. ‘현장 확인 필요’로 표시된 곳은 저희도 모르는 정보예요.',
        ],
      },
      { title: '3. 계정', body: ['로그인 없이도 이 기기에 여행을 저장해 쓸 수 있어요. 가입하면 여행과 패치가 계정에 저장돼요.'] },
      { title: '4. 책임의 한계', body: ['[작성 필요: 이동 시간·영업시간 추정의 오차, 외부 데이터(Google 지도) 오류에 대한 책임 범위]'] },
      { title: '5. 약관의 변경', body: ['약관이 바뀌면 시행일 전에 앱에서 알리고, 다시 동의를 받아요.'] },
    ],
  },
  privacy: {
    title: '개인정보 처리방침',
    sections: [
      {
        title: '1. 처리하는 개인정보 항목',
        body: [
          '이메일 가입: 이메일, 비밀번호(Supabase가 암호화해 저장, 운영자는 볼 수 없음), 닉네임 — 필수',
          'Google 로그인: Google 계정 식별값, 이메일, 프로필 이름 — 필수',
          '서비스 이용: 여행지, 여행 날짜, 등록한 일정의 제목·시각·중요도, 장소 ID(Google place_id), 패치 기록 — 필수',
          '위치 정보는 수집하지 않아요. 지금 있는 곳은 사용자가 일정 중에서 직접 골라요.',
          '자동 수집: [작성 필요: 접속 기록 등]',
        ],
      },
      {
        title: '2. 처리 목적',
        body: ['회원 관리, 여행 일정 정리, 일정이 깨졌을 때 패치 계산, 서비스 개선을 위한 통계(개인을 알아볼 수 없게)'],
      },
      { title: '3. 보유 및 이용 기간', body: ['탈퇴하면 바로 지워요. 법령에 따라 보관해야 하는 정보: [작성 필요: 항목·기간]'] },
      {
        title: '4. 처리 위탁 · 국외 이전',
        body: [
          'Supabase(계정·데이터 저장)',
          'Google(장소 검색·영업시간 조회, 장소 이름과 좌표는 저장하지 않음)',
          'OpenAI(붙여넣은 일정과 상황 문장을 구조화. 계정 정보는 보내지 않음)',
          '[작성 필요: 각 업체의 소재국, 이전 일시·방법, 보유 기간]',
        ],
      },
      { title: '5. 이용자의 권리', body: ['설정에서 정보를 고치거나 탈퇴할 수 있어요. 탈퇴하면 여행과 패치 기록이 함께 지워져요.'] },
      { title: '6. 개인정보 보호책임자', body: ['[작성 필요: 이름 · 연락처]'] },
    ],
  },
}

export default function Legal() {
  const { doc = 'terms' } = useParams()
  const page = DOCS[doc]
  if (!page) return <NotFound />
  return (
    <article className="account account__legal">
      <nav className="account__legal-tabs" aria-label="약관과 정책">
        {Object.entries(DOCS).map(([key, d]) => (
          <Link key={key} to={`/legal/${key}`} aria-current={key === doc ? 'page' : undefined}>
            {d.title}
          </Link>
        ))}
      </nav>
      <h1>{page.title}</h1>
      <p className="account__hint">버전 {TERMS_VERSION} · 시행일 [작성 필요]</p>
      {page.sections.map((s) => (
        <section key={s.title}>
          <h2>{s.title}</h2>
          {s.body.map((b) => (
            <p key={b}>{b}</p>
          ))}
        </section>
      ))}
    </article>
  )
}
