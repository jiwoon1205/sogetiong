/* eslint-disable @next/next/no-img-element */
import { avatarUrl, type BoardAuthor } from "@/lib/board";

/** 게시판 프사. 직접 올린 사진이 없으면 인스타처럼 기본 그림 (2026-11-22) */
export function BoardAvatar({ author, size = 36 }: { author: Pick<BoardAuthor, "id" | "has_avatar" | "avatar_version">; size?: number }) {
  const url = avatarUrl(author);
  if (url) {
    return <img src={url} alt="" width={size} height={size} className="shrink-0 rounded-full border border-line object-cover" style={{ width: size, height: size }} />;
  }
  return (
    <span aria-hidden className="flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-line" style={{ width: size, height: size }}>
      <svg viewBox="0 0 40 40" width={size} height={size}>
        <circle cx="20" cy="15" r="7" fill="#F6F3EE" />
        <path d="M6 37c1.5-8 7-12 14-12s12.5 4 14 12" fill="#F6F3EE" />
      </svg>
    </span>
  );
}
