import { BoardAvatar } from "@/components/board/BoardAvatar";
import type { BoardAuthor } from "@/lib/board";
import { cn, shortSchoolName } from "@/lib/format";

/** <프사> <닉네임> <성별> · 학교(캠퍼스) <점수>. 소개팅 프로필은 절대 안 보인다. */
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
      <span className="min-w-0 flex-1 text-left">
        <span className="flex min-w-0 items-center gap-1.5">
          <span className={cn("truncate text-[14px] font-semibold", author.deleted ? "text-ink-faint" : "text-ink")}>{author.nickname}</span>
          {author.gender && <GenderMark gender={author.gender} />}
          {author.score && (
            <span className="num shrink-0 rounded bg-paper-deep px-1.5 py-0.5 text-[11px] text-ink-soft">
              {author.score.label} {author.score.value}
            </span>
          )}
          {badge}
        </span>
        {author.school && (
          <span className="block truncate text-[12px] text-ink-faint">
            {shortSchoolName(author.school)}
            {author.campus ? ` · ${author.campus}` : ""}
          </span>
        )}
      </span>
      {trailing}
    </>
  );
  return clickable ? (
    <button type="button" onClick={onClick} className="flex w-full min-w-0 items-center gap-2.5">
      {Inner}
    </button>
  ) : (
    <div className="flex w-full min-w-0 items-center gap-2.5">{Inner}</div>
  );
}

export function GenderMark({ gender }: { gender: "MALE" | "FEMALE" }) {
  return (
    <span className={cn("shrink-0 text-[12px] font-semibold", gender === "FEMALE" ? "text-brick" : "text-[#3E6A8A]")} aria-label={gender === "FEMALE" ? "여성" : "남성"}>
      {gender === "FEMALE" ? "♀" : "♂"}
    </span>
  );
}
