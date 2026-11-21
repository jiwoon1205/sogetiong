"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthorLine } from "@/components/board/AuthorLine";
import { BoardReportModal } from "@/components/board/BoardReportModal";
import { SuperLikeBuy } from "@/components/SuperLike";
import { Button, Modal, Notice, Spinner, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { BoardAuthor, BoardMe, NoteRoom } from "@/lib/board";

type ProfileInfo = { profile: BoardAuthor; note_room_id: string | null; note_room_closed: boolean };

/**
 * 글·댓글 작성자를 눌렀을 때 뜨는 카드 (2026-11-22).
 * 게시판 프로필만 보인다 (소개팅 프로필은 안 보임). 쪽지 보내기 · 신고 · 차단.
 * 쪽지: 슈퍼 라이크 1개 (여성은 하루 3개 무료). 상대가 답장하기 전에는 1개만.
 */
type SheetProps = {
  profileId: string | null;
  postId?: string;
  me: BoardMe;
  onClose: () => void;
  onBlocked?: () => void;
  onSpent?: () => void;
};

export function ProfileSheet(props: SheetProps) {
  return props.profileId ? <Sheet key={props.profileId} {...props} /> : null;
}

function Sheet({
  profileId,
  postId,
  me,
  onClose,
  onBlocked,
  onSpent,
}: SheetProps) {
  const router = useRouter();
  const [info, setInfo] = useState<ProfileInfo | null>(null);
  const [error, setError] = useState("");
  const [writing, setWriting] = useState(false);
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [reporting, setReporting] = useState(false);
  const [confirmBlock, setConfirmBlock] = useState(false);

  useEffect(() => {
    if (!profileId) return;
    api<ProfileInfo>(`/board/profiles/${profileId}`)
      .then(setInfo)
      .catch((e) => setError(errorMessage(e)));
  }, [profileId]);

  const free = me.free_notes_left;
  const costText =
    free !== null && free > 0
      ? `오늘 무료 쪽지 ${free}개 남음 (여성 하루 ${me.config.free_notes_per_day}개 무료)`
      : `슈퍼 라이크 1개 사용 · 남은 슈퍼 라이크 ${me.super_likes.count}개`;
  const noSuperLike = !(free !== null && free > 0) && me.super_likes.count < 1;
  const banned = Boolean(me.profile?.banned_until);

  async function send() {
    if (!profileId) return;
    setSending(true);
    setError("");
    try {
      const r = await api<{ room: NoteRoom; new: boolean }>("/notes", { method: "POST", body: { board_profile_id: profileId, body, post_id: postId ?? null } });
      onSpent?.();
      router.push(`/notes/${r.room.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSending(false);
    }
  }

  async function block() {
    if (!profileId) return;
    try {
      await api("/board/blocks", { method: "POST", body: { board_profile_id: profileId } });
      onBlocked?.();
      onClose();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  return (
    <>
      <Modal open onClose={onClose} title="게시판 프로필">
        {!info && !error ? (
          <Spinner />
        ) : (
          <div className="space-y-5">
            {info && <AuthorLine author={info.profile} size={52} />}
            {error && <Notice tone="error">{error}</Notice>}
            {info && !writing && (
              <div className="space-y-2">
                {info.note_room_id ? (
                  info.note_room_closed ? (
                    <p className="text-center text-[13.5px] text-ink-faint">이 사람과의 쪽지는 끝났어요.</p>
                  ) : (
                    <Link href={`/notes/${info.note_room_id}`} className="flex h-11 w-full items-center justify-center rounded-md bg-ink text-[15px] font-medium text-paper">
                      쪽지방으로 가기
                    </Link>
                  )
                ) : (
                  <Button className="w-full" disabled={banned} onClick={() => setWriting(true)}>
                    ✉️ 쪽지 보내기
                  </Button>
                )}
                {banned && <p className="text-center text-[12.5px] text-brick">게시판 이용 정지 중에는 쪽지를 보낼 수 없어요.</p>}
                <div className="grid grid-cols-2 gap-2 pt-1">
                  <Button variant="secondary" size="sm" onClick={() => setReporting(true)}>
                    신고
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => setConfirmBlock(true)}>
                    차단
                  </Button>
                </div>
                {confirmBlock && (
                  <div className="rounded-md border border-line bg-paper-deep p-3 text-[13px] text-ink-soft">
                    차단하면 서로의 글·댓글·쪽지가 보이지 않고, 소개팅 추천에도 서로 안 나와요. 상대에게 알리지 않아요.
                    <Button variant="danger" size="sm" className="mt-2 w-full" onClick={block}>
                      차단하기
                    </Button>
                  </div>
                )}
              </div>
            )}
            {info && writing && (
              <div className="space-y-3">
                <Textarea
                  value={body}
                  autoFocus
                  rows={4}
                  maxLength={me.config.note_max}
                  placeholder="첫 쪽지를 적어 주세요. 상대가 답장하기 전에는 1개만 보낼 수 있어요."
                  onChange={(e) => setBody(e.target.value)}
                />
                <p className="text-[12.5px] text-ink-faint">{costText}</p>
                {noSuperLike ? (
                  <div className="rounded-md border border-line p-3">
                    <p className="mb-3 text-[13px] text-ink-soft">쪽지를 보내려면 슈퍼 라이크가 필요해요 (1개 {me.config.super_like_price.toLocaleString()}원).</p>
                    <SuperLikeBuy onBought={() => onSpent?.()} />
                  </div>
                ) : (
                  <Button className="w-full" loading={sending} disabled={!body.trim()} onClick={send}>
                    보내기
                  </Button>
                )}
                <Button variant="ghost" size="sm" className="w-full" onClick={() => setWriting(false)}>
                  취소
                </Button>
              </div>
            )}
          </div>
        )}
      </Modal>
      <BoardReportModal target={reporting && profileId ? { type: "PROFILE", id: profileId } : null} onClose={() => setReporting(false)} />
    </>
  );
}
