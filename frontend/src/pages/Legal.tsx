import { Link, useParams } from 'react-router'
import { TERMS_VERSION } from '../lib/supabase'
import NotFound from './NotFound'
import './Account.css'

// Every statement here describes what the code and deployment really do (render.yaml, vercel.json,
// supabase/migrations, guest_quota.py). If one of those changes, change the text with it.
const OPERATOR = '양규림'
const CONTACT = 'kyurim1006@gmail.com'
const EFFECTIVE_DATE = TERMS_VERSION

// A body is a run of blocks: a plain string is a paragraph, { li } a bullet, { k, v } a labelled
// row. Consecutive bullets / rows are grouped into one list so their columns line up.
type Row = { k: string; v: string[] }
type Block = string | { li: string } | Row
type Section = { title: string; body: Block[] }
const DOCS: Record<string, { title: string; sections: Section[] }> = {
  terms: {
    title: '이용약관',
    sections: [
      {
        title: '제1조 목적',
        body: [
          `이 약관은 ${OPERATOR}(이하 ‘운영자’)가 제공하는 여행 일정 복구 서비스 TravelPatch(이하 ‘서비스’)를 이용하는 조건과 절차, 운영자와 이용자의 권리·의무를 정해요.`,
        ],
      },
      {
        title: '제2조 용어',
        body: [
          '‘이용자’는 이 약관에 따라 서비스를 쓰는 사람이에요. 가입한 ‘회원’과 가입하지 않은 ‘게스트’가 있어요.',
          '‘일정’은 이용자가 등록한 여행 계획이고, ‘패치’는 일정이 깨졌을 때 서비스가 계산해 제안하는 원래 일정에 대한 변경 목록이에요.',
        ],
      },
      {
        title: '제3조 약관의 효력과 변경',
        body: [
          '이 약관은 서비스 화면에 게시하고, 가입하거나 처음 로그인할 때 동의를 받아 효력이 생겨요.',
          '약관을 바꿀 때는 시행일 7일 전부터 서비스 안에 알려요. 이용자에게 불리한 변경은 30일 전부터 알려요. 바뀐 약관은 다음 로그인 때 다시 동의를 받고, 동의하지 않으면 탈퇴할 수 있어요.',
        ],
      },
      {
        title: '제4조 서비스 내용',
        body: [
          '붙여넣거나 직접 입력한 여행 일정을 정리하고 장소를 찾아 연결해요.',
          '여행 중 늦잠·비·휴무·체력 저하 같은 상황을 알려 주면, 원래 일정을 최대한 지키는 패치 후보를 계산해 보여 줘요. 각 변경에는 이유가 함께 나와요.',
          '서비스는 무료예요. 개인이 운영하는 프로젝트라 기능과 운영 방식이 바뀔 수 있어요.',
        ],
      },
      {
        title: '제5조 회원 가입과 계정',
        body: [
          '만 14세 이상만 가입할 수 있어요. 이메일 또는 Google 계정으로 가입해요.',
          '가입하지 않아도 이 기기(브라우저)에 여행을 저장해 쓸 수 있어요. 이 경우 브라우저 데이터를 지우면 여행도 사라져요.',
          '계정과 비밀번호는 본인이 관리해야 해요. 다른 사람이 내 계정을 쓰고 있다고 의심되면 바로 비밀번호를 바꾸고 운영자에게 알려 주세요.',
        ],
      },
      {
        title: '제6조 이용 제한',
        body: [
          '일정 정리와 장소 검색은 외부 유료 서비스를 쓰기 때문에, 게스트는 하루에 쓸 수 있는 횟수가 정해져 있어요. 한도를 넘으면 다음 날 다시 쓰거나 가입해 주세요.',
          '다음 행위를 하면 서비스 이용을 제한하거나 계정을 정지할 수 있어요.',
          { li: '자동화 도구로 대량 요청하기' },
          { li: '다른 사람의 정보로 가입하기' },
          { li: '서비스나 서버의 정상 운영을 방해하기' },
          { li: '법령을 어기는 내용을 등록하기' },
        ],
      },
      {
        title: '제7조 이용자가 등록한 내용',
        body: [
          '이용자가 등록한 일정과 패치 기록의 권리는 이용자에게 있어요. 운영자는 서비스를 제공하는 데 필요한 범위에서만 그 내용을 처리해요.',
          '개인을 알아볼 수 없게 가공한 통계는 서비스 개선과 연구·발표 자료에 쓸 수 있어요.',
        ],
      },
      {
        title: '제8조 서비스의 변경과 중단',
        body: [
          '점검, 외부 서비스(Google·OpenAI·Supabase 등) 장애, 운영상 이유로 서비스 일부나 전부가 잠시 멈출 수 있어요. 미리 알 수 있는 중단은 서비스 안에 알려요.',
          '서비스를 끝낼 때는 30일 전에 알리고, 그동안 이용자는 자기 기록을 확인할 수 있어요. 종료 후 개인정보는 개인정보 처리방침에 따라 지워요.',
        ],
      },
      {
        title: '제9조 책임의 한계',
        body: [
          '패치는 계산된 제안이에요. 이동 시간은 장소 사이 직선거리로 추정한 값이라 실제와 다를 수 있어요. 영업시간·휴무·예약 상태도 외부 데이터라 틀릴 수 있어요.',
          '‘현장 확인 필요’로 표시된 항목은 서비스가 모르는 정보예요. 실제 운영 여부와 예약은 직접 확인해 주세요.',
          '운영자는 패치를 따르거나 외부 데이터가 틀려서 생긴 손해(예약 취소 수수료, 교통비 등)에 대해, 운영자의 고의 또는 중대한 과실이 없는 한 책임지지 않아요. 서비스는 예약을 대신 하거나 바꾸지 않아요.',
        ],
      },
      {
        title: '제10조 탈퇴',
        body: ['회원은 언제든 탈퇴할 수 있어요. 방법과 지워지는 정보는 개인정보 처리방침 ‘이용자의 권리’에 적혀 있어요.'],
      },
      {
        title: '제11조 준거법과 분쟁',
        body: [
          '이 약관은 대한민국 법을 따라요. 분쟁이 생기면 먼저 운영자와 이야기해 해결하고, 소송이 필요하면 민사소송법에 따른 관할 법원에서 다퉈요.',
          `문의: ${CONTACT}`,
        ],
      },
    ],
  },
  privacy: {
    title: '개인정보 처리방침',
    sections: [
      {
        title: '1. 처리하는 개인정보 항목',
        body: [
          { k: '이메일 가입', v: ['이메일, 비밀번호, 닉네임 (필수)', '비밀번호는 Supabase가 해시로 바꿔 저장해서 운영자도 볼 수 없어요.'] },
          { k: 'Google 로그인', v: ['Google 계정 식별값, 이메일, 프로필 이름, 서비스에서 정한 닉네임 (필수)'] },
          { k: '동의 기록', v: ['동의한 약관 버전, 만 14세 이상 확인, 동의 시각 (필수)'] },
          {
            k: '서비스 이용',
            v: [
              '여행지, 여행 날짜, 숙소·공항과 일정 장소의 이름·Google 장소 ID(place_id), 일정의 시각·중요도·메모, 확정한 패치 기록 (회원, 필수)',
              '장소 좌표는 조회 후 30일이 지나면 지워요.',
            ],
          },
          {
            k: '자동 수집',
            v: [
              '접속 IP 주소, 접속 시각, 요청 기록',
              '하루 이용 횟수를 세는 데 IP를 써요. IP는 그대로 저장하지 않고, 알아볼 수 없게 바꾼 값(암호화 해시)만 이틀 동안 보관한 뒤 지워요. 호스팅 업체(Vercel·Render·Supabase)는 운영 로그에 접속 기록을 남겨요.',
            ],
          },
          '위치 정보(GPS)는 수집하지 않아요. 지금 있는 곳은 이용자가 일정 중에서 직접 골라요.',
          '게스트의 여행은 서버가 아니라 이 브라우저의 저장소(localStorage)에만 저장돼요.',
        ],
      },
      {
        title: '2. 처리 목적',
        body: [
          { li: '회원 가입과 로그인, 본인 확인, 약관 동의 관리' },
          { li: '여행 일정 정리, 장소 연결, 일정이 깨졌을 때 패치 계산과 저장' },
          { li: '부정 이용 방지(게스트 이용 횟수 제한 포함)와 서비스 안정성 유지' },
          { li: '개인을 알아볼 수 없게 가공한 통계로 서비스 개선' },
          '광고나 마케팅에는 쓰지 않고, 개인정보를 팔거나 제3자에게 제공하지 않아요.',
        ],
      },
      {
        title: '3. 보유 및 이용 기간',
        body: [
          '회원 정보와 여행·패치 기록은 탈퇴할 때까지 보관하고, 탈퇴하면 지체 없이 지워요. 동의 기록도 계정과 함께 지워요.',
          '서비스는 무료이고 결제가 없어서, 법령에 따라 따로 보관하는 정보는 현재 없어요. 수사기관이 법에 따라 요청하면 그때 남아 있는 범위에서만 제공해요.',
          '호스팅 업체의 운영 로그는 각 업체 정책에 따라 짧은 기간 보관 후 자동으로 지워져요.',
        ],
      },
      {
        title: '4. 처리 위탁',
        body: [
          '서비스 운영을 위해 아래 업체에 처리를 맡겨요. 업체가 맡은 일 외에 정보를 쓰지 않도록 각 업체 약관과 데이터 처리 조건에 따라 관리해요.',
          { k: 'Supabase', v: ['회원 인증, 데이터베이스 저장'] },
          { k: 'Vercel', v: ['웹사이트 제공, 요청 전달'] },
          { k: 'Render', v: ['서버 운영'] },
          { k: 'OpenAI', v: ['붙여넣은 일정과 상황 문장을 구조화하고, 휴무인 곳을 대신할 장소 종류 고르기'] },
          { k: 'Google', v: ['로그인(Google 로그인을 쓸 때), 장소 검색과 장소 정보(좌표·영업시간) 조회'] },
        ],
      },
      {
        title: '5. 국외 이전',
        body: [
          '위 업체 중 일부는 해외에서 정보를 처리해요. 서비스를 이용하는 순간마다 암호화된 네트워크(HTTPS)로 전송돼요. 이전을 거부하려면 서비스를 쓰지 않거나 탈퇴하면 되지만, 그러면 서비스를 이용할 수 없어요.',
          { k: 'Supabase', v: ['위치: 대한민국(서울 리전)', '항목: 1항의 회원·이용 정보 전부', '보유: 탈퇴할 때까지'] },
          { k: 'Render', v: ['위치: 싱가포르', '항목: 요청 내용(일정·상황 문장·장소 ID)과 IP', '보유: 처리 후 버림(운영 로그 제외)'] },
          { k: 'Vercel', v: ['위치: 미국 등 Vercel의 전 세계 서버', '항목: 요청 내용과 IP', '보유: 저장하지 않음(운영 로그 제외)'] },
          {
            k: 'OpenAI',
            v: [
              '위치: 미국',
              '항목: 붙여넣은 일정 글, 상황 문장, 일정 제목·시각 (이메일·닉네임 같은 계정 정보는 보내지 않아요)',
              '보유: OpenAI API 정책에 따라 오남용 감시 목적으로 최대 30일 보관 후 삭제, 학습에 쓰지 않음',
            ],
          },
          {
            k: 'Google',
            v: [
              '위치: 미국',
              '항목: 장소 검색어와 장소 ID, Google 로그인 시 계정 정보',
              '보유: Google 정책에 따름 (서비스는 장소 ID를 저장하고, 좌표는 30일까지만 저장해요)',
            ],
          },
        ],
      },
      {
        title: '6. 파기 방법',
        body: [
          '데이터베이스의 정보는 복구할 수 없게 삭제해요. 계정을 지우면 연결된 여행·패치·동의 기록이 함께 지워지도록 데이터베이스에 묶여 있어요.',
          '브라우저에 저장된 게스트 여행은 앱에서 여행을 지우거나 브라우저 데이터를 지우면 사라져요.',
        ],
      },
      {
        title: '7. 이용자의 권리와 행사 방법',
        body: [
          '이용자는 언제든 자기 개인정보를 보거나 고치거나 지우거나 처리를 멈추라고 요구할 수 있어요.',
          '닉네임과 여행은 앱에서 바로 고치거나 지울 수 있어요.',
          '설정 > 탈퇴하기에서 바로 탈퇴할 수 있어요. 탈퇴하면 계정과 여행·패치 기록, 동의 기록을 서버에서 바로 지워요.',
          `앱에서 할 수 없는 요청은 가입한 이메일로 ${CONTACT}에 보내 주세요. 본인 확인 후 10일 안에 처리하고 결과를 알려 드려요.`,
          '만 14세 미만은 가입할 수 없어요. 만 14세 미만의 정보가 수집된 것을 알게 되면 바로 지워요.',
        ],
      },
      {
        title: '8. 안전성 확보 조치',
        body: [
          { li: '모든 통신은 HTTPS로 암호화해요.' },
          { li: '데이터베이스 행 수준 보안(RLS)으로 각 회원은 자기 데이터만 읽고 쓸 수 있어요.' },
          { li: '서버 비밀키는 저장소에 올리지 않고 호스팅 설정에만 두며, 데이터에 접근할 수 있는 사람은 운영자 한 명뿐이에요.' },
        ],
      },
      {
        title: '9. 쿠키와 브라우저 저장소',
        body: [
          '광고·추적 쿠키나 방문 분석 도구는 쓰지 않아요.',
          '로그인 상태 유지와 게스트 여행 저장을 위해 브라우저 저장소(localStorage)를 써요. 브라우저 설정에서 지울 수 있고, 지우면 로그아웃되고 게스트 여행이 사라져요.',
        ],
      },
      {
        title: '10. 개인정보 보호책임자',
        body: [
          { k: '책임자', v: [OPERATOR] },
          { k: '연락처', v: [CONTACT] },
          '개인정보 침해에 대한 신고나 상담은 아래 기관에도 할 수 있어요.',
          { k: '개인정보침해 신고센터', v: ['privacy.kisa.or.kr', '국번 없이 118'] },
          { k: '개인정보 분쟁조정위원회', v: ['www.kopico.go.kr', '1833-6972'] },
          { k: '대검찰청 사이버수사과', v: ['www.spo.go.kr', '국번 없이 1301'] },
          { k: '경찰청 사이버수사국', v: ['ecrm.police.go.kr', '국번 없이 182'] },
        ],
      },
      {
        title: '11. 처리방침의 변경',
        body: ['이 방침이 바뀌면 시행일 7일 전부터 서비스 안에 알리고, 중요한 변경은 다시 동의를 받아요.'],
      },
    ],
  },
}

type Group = { kind: 'p'; text: string } | { kind: 'ul'; items: string[] } | { kind: 'dl'; rows: Row[] }

function groups(body: Block[]): Group[] {
  const out: Group[] = []
  for (const b of body) {
    const last = out[out.length - 1]
    if (typeof b === 'string') out.push({ kind: 'p', text: b })
    else if ('li' in b) {
      if (last?.kind === 'ul') last.items.push(b.li)
      else out.push({ kind: 'ul', items: [b.li] })
    } else if (last?.kind === 'dl') last.rows.push(b)
    else out.push({ kind: 'dl', rows: [b] })
  }
  return out
}

function renderGroup(g: Group, i: number) {
  if (g.kind === 'p') return <p key={i}>{g.text}</p>
  if (g.kind === 'ul')
    return (
      <ul key={i} className="account__legal-list">
        {g.items.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
    )
  return (
    <dl key={i} className="account__legal-rows">
      {g.rows.map((r) => (
        <div key={r.k}>
          <dt>{r.k}</dt>
          <dd>
            {r.v.map((line) => (
              <span key={line}>{line}</span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  )
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
      <header className="account__legal-head">
        <h1>{page.title}</h1>
        <p className="account__hint">버전 {TERMS_VERSION} · 시행일 {EFFECTIVE_DATE}</p>
      </header>
      {page.sections.map((s) => (
        <section key={s.title}>
          <h2>{s.title}</h2>
          {groups(s.body).map(renderGroup)}
        </section>
      ))}
    </article>
  )
}
