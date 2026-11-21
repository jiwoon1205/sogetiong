import { BoardAvatar } from "@/components/board/BoardAvatar";
import type { BoardAuthor } from "@/lib/board";
import { cn, shortSchoolName } from "@/lib/format";

/** <프사> <닉네임> <학교(캠퍼스)> <점수> <성별> 한 줄. 소개팅 프로필은 절대 안 보인다. */
export function AuthorLine({
  author,
  size = 32,
  onClick,
  trailing,
  badge,
}: {
  author: BoardAuthor;
  size?: number;
  onClick?: () => void;
  trailing?: React.ReactNode;
  badge?: React.ReactNode;
}) {
  const clickable = Boolean(onClick) && !author.deleted;
  const Inner = (
    <>
      <BoardAvatar author={author} size={size} />
      {/* 한 줄 (2026-11-22): 닉네임 · 학교(캠퍼스) · 점수 · 성별. 길면 닉네임·학교가 말줄임 */}
      <span className="flex min-w-0 flex-1 items-center gap-1.5 text-left">
        <span className={cn("min-w-0 shrink truncate text-[14px] font-semibold", author.deleted ? "text-ink-faint" : "text-ink")}>{author.nickname}</span>
        {author.school && (
          <span className="min-w-0 shrink-[2] truncate text-[12px] text-ink-faint">
            {shortSchoolName(author.school)}
            {author.campus ? ` ${author.campus}` : ""}
          </span>
        )}
        {author.score && (
          <span className="num shrink-0 rounded bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-soft">
            {author.score.label} {author.score.value}
          </span>
        )}
        {author.gender && <GenderMark gender={author.gender} />}
        {badge}
      </span>
    </>
  );
  // 오른쪽 끝(trailing: 신고 버튼 등)은 누르는 영역 밖에 둔다 (버튼 안에 버튼이 들어가지 않게)
  return (
    <div className="flex w-full min-w-0 items-center gap-2">
      {clickable ? (
        <button type="button" onClick={onClick} className="flex min-w-0 flex-1 items-center gap-2.5">
          {Inner}
        </button>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-2.5">{Inner}</div>
      )}
      {trailing}
    </div>
  );
}

export function GenderMark({ gender }: { gender: "MALE" | "FEMALE" }) {
  return (
    <span className={cn("shrink-0 text-[12px] font-semibold", gender === "FEMALE" ? "text-brick" : "text-[#3E6A8A]")} aria-label={gender === "FEMALE" ? "여성" : "남성"}>
      {gender === "FEMALE" ? "♀" : "♂"}
    </span>
  );
}
