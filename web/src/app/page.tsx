import { Brand } from "@/components/Brand";
import { SupportContact } from "@/components/SupportContact";
import { ButtonLink } from "@/components/ui";

const PRINCIPLES = [
  {
    no: "01",
    title: "학교 메일로 확인된 사람만",
    body: "재학생 이메일 인증을 마친 같은 학교 학생만 들어올 수 있습니다.",
  },
  {
    no: "02",
    title: "이름과 얼굴은 나중에",
    body: "실명·학번·사진은 다른 학생에게 보이지 않습니다. 사진은 AI가 평가하고, 네 가지 항목의 점수로만 전해집니다.",
  },
  {
    no: "03",
    title: "서로 좋아요를 눌렀을 때만",
    body: "좋아요는 하루 5개(VIP는 5+5개)라 한 사람 한 사람 신중하게 고르게 됩니다. 서로 마음이 맞으면 바로 대화할 수 있어요.",
  },
];

export default function Landing() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-6 sm:px-8">
        <Brand />
        <nav className="flex items-center gap-1">
          <ButtonLink href="/login" variant="ghost" size="sm">
            로그인
          </ButtonLink>
          <ButtonLink href="/signup" variant="secondary" size="sm">
            시작하기
          </ButtonLink>
        </nav>
      </header>

      <main className="mx-auto max-w-5xl px-5 sm:px-8">
        <section className="grid gap-10 pb-16 pt-10 sm:pt-20 md:grid-cols-[1.25fr_1fr] md:gap-16">
          <div>
            <p className="eyebrow mb-6">한국외국어대학교 재학생 전용</p>
            <h1 className="font-serif text-[40px] font-semibold leading-[1.18] tracking-tight sm:text-[54px]">
              누군지는 몰라도,
              <br />
              어떤 사람인지는
              <br />
              <span className="text-brick">충분히 알 수 있게.</span>
            </h1>
            <p className="mt-7 max-w-md text-[16px] leading-[1.75] text-ink-soft">
              같은 학교 학생이라는 것만 확인된 채로 시작합니다. 사진 대신 취향과 이야기로 먼저 만나고,
              신뢰가 쌓인 다음에 서로 원하는 만큼만 알아가세요.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <ButtonLink href="/signup" size="lg">
                학교 메일로 시작하기
              </ButtonLink>
              <ButtonLink href="/login" size="lg" variant="secondary">
                이미 계정이 있어요
              </ButtonLink>
            </div>
          </div>

          {/* 카드 미리보기 — 실제 서비스 카드와 같은 모양 */}
          <aside aria-hidden className="relative hidden md:block">
            <div className="absolute -right-2 top-6 h-full w-full rotate-[2.5deg] rounded-card border border-line bg-paper-deep" />
            <div className="relative rounded-card border border-line bg-paper-card p-7">
              <p className="font-serif text-[22px] font-semibold">새벽의 산책자</p>
              <p className="mt-1 text-[13.5px] text-ink-soft">22세 · 서울캠퍼스</p>
              <div className="rule my-5" />
              <p className="eyebrow mb-3">외적 특징 · AI 평가</p>
              {[
                ["전체적인 인상", 8],
                ["스타일", 7],
                ["자기관리", 8],
                ["사진 분위기", 9],
              ].map(([l, v]) => (
                <div key={l} className="mb-2.5 grid grid-cols-[5.5rem_1fr_1.5rem] items-center gap-3">
                  <span className="text-[12.5px] text-ink-soft">{l}</span>
                  <span className="relative h-[3px] rounded-full bg-line">
                    <span className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${Number(v) * 10}%` }} />
                  </span>
                  <span className="num text-right text-[13px] font-semibold">{v}</span>
                </div>
              ))}
              <div className="rule my-5" />
              <p className="text-[14px] leading-relaxed">
                비 오는 날 동네 서점 가는 걸 좋아해요. 대화가 길어져도 지루하지 않은 사람이면 좋겠어요.
              </p>
              <p className="mt-4 text-[13px] text-ink-faint">독서 · 산책 · 전시</p>
            </div>
          </aside>
        </section>

        <section className="grid gap-px overflow-hidden rounded-card border border-line bg-line md:grid-cols-3">
          {PRINCIPLES.map((p) => (
            <div key={p.no} className="bg-paper p-7">
              <p className="num text-[12px] font-semibold text-brick">{p.no}</p>
              <h2 className="mt-4 text-[17px] font-semibold">{p.title}</h2>
              <p className="mt-2.5 text-[14px] leading-[1.7] text-ink-soft">{p.body}</p>
            </div>
          ))}
        </section>

        <footer className="flex flex-col gap-2 py-12 text-[12.5px] text-ink-faint sm:flex-row sm:justify-between">
          <div className="space-y-1">
            <p>만 18세 이상 재학생만 이용할 수 있습니다.</p>
            <p>
              <SupportContact />
            </p>
          </div>
          <p>
            <a href="/privacy" className="underline underline-offset-4">
              개인정보처리방침
            </a>
          </p>
        </footer>
      </main>
    </div>
  );
}
