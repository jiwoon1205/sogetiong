"use client";

/**
 * 추천 탭 "추천 방식 ⓘ" 설명 (2026-10-24).
 * 서버 추천 규칙(matching_service.weight)을 사용자 말로 풀어 쓴 것. 외모 등급(내부 전용)은 절대 적지 않는다.
 */

import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/ui";
import { BIO_FULL, IDEAL_FULL, INTEREST_MAX } from "@/lib/profileEffort";

export function RecommendGuideButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-[12.5px] text-ink-faint underline-offset-2 hover:text-ink hover:underline"
      >
        추천 방식 ⓘ
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="추천은 이렇게 골라요">
        <RecommendGuide onClose={() => setOpen(false)} />
      </Modal>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[13.5px] font-semibold text-ink">{title}</h3>
      <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink-soft">{children}</ul>
    </section>
  );
}

function Item({ children }: { children: React.ReactNode }) {
  return <li className="flex gap-2"><span className="text-ink-faint">·</span><span>{children}</span></li>;
}

function RecommendGuide({ onClose }: { onClose: () => void }) {
  return (
    <div className="space-y-5">
      <p className="text-[13px] leading-relaxed text-ink-soft">
        추천은 들어올 때마다 새로 뽑아요. 아래 조건에 맞을수록 <b className="font-semibold text-ink">뽑힐 확률이 올라갈 뿐</b>, 순서가
        정해져 있지 않아서 누구에게나 기회가 있어요.
      </p>

      <Section title="누가 나오나요">
        <Item>나와 상대의 조건(성별·나이·학교·캠퍼스·같은 학과 제외)이 <b className="font-semibold text-ink">서로</b> 맞는 사람만 나와요.</Item>
        <Item>사진 검수가 끝난 학생만 나와요.</Item>
        <Item>이미 매칭됐거나 차단한 사람은 나오지 않아요.</Item>
      </Section>

      <Section title="이런 사람이 더 자주 나와요">
        <Item>최근 2주 동안 자주 접속한 사람</Item>
        <Item>나에게 좋아요를 보낸 사람 — 여러 번 보냈을수록 더 자주</Item>
        <Item>나와 관심사가 겹치는 사람 (많이 겹칠수록), MBTI가 비슷한 사람</Item>
        <Item>프로필을 정성껏 쓴 사람</Item>
      </Section>

      <Section title="다시 나오는 경우">
        <Item>넘긴 사람은 2일 뒤에 다시 나올 수 있어요.</Item>
        <Item>
          좋아요를 보냈는데 2일 동안 매칭이 안 되면 다시 나와요. 또 좋아요를 보낼 수 있고, 보낼수록 상대 추천에 내가 더 자주 나와요.
        </Item>
        <Item>
          같은 사람에게 좋아요가 <b className="font-semibold text-ink">5번</b> 쌓이면 상대가 좋아요하지 않아도 바로 매칭돼요 (슈퍼 라이크와 같아요).
        </Item>
        <Item>⭐ 슈퍼 라이크는 보내는 즉시 매칭돼요.</Item>
      </Section>

      <div className="space-y-2 rounded-card border border-line bg-paper-deep/50 p-4">
        <h3 className="text-[13.5px] font-semibold text-ink">내 프로필이 더 자주 나오려면</h3>
        <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink-soft">
          <Item>자기소개를 띄어쓰기 빼고 <b className="font-semibold text-ink">{BIO_FULL}자 이상</b> (휴대폰에서 약 5줄)</Item>
          <Item>이상형을 <b className="font-semibold text-ink">{IDEAL_FULL}자 이상</b></Item>
          <Item>MBTI·얼굴상·키 입력하기</Item>
          <Item>관심사는 나와 꼭 맞는 {INTEREST_MAX}개 고르기 (많이 고른다고 유리하지 않아요, 겹쳐야 올라가요)</Item>
          <Item>자주 들어오기</Item>
        </ul>
        <p className="text-[12px] text-ink-faint">같은 글자만 반복한 글(ㅋㅋㅋ…)은 글자 수로 치지 않아요.</p>
        <Link href="/profile" onClick={onClose} className="inline-block pt-1 text-[13px] font-medium text-brick underline-offset-2 hover:underline">
          내 프로필 다듬기 →
        </Link>
      </div>
    </div>
  );
}
