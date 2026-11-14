"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Button, Notice, Spinner } from "@/components/ui";
import { adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";

type Member = { user_id: string; subject_code: string; nickname: string | null };
/** 2026-11-14: 사진·인스타 교환. 관리자는 1회용 사진(90일 보관)과 두 사람의 인스타 아이디(수락 전·거절 포함)를 모두 본다 */
type Msg = {
  message_id: string;
  type?: "TEXT" | "PHOTO" | "INSTA_REQUEST" | "INSTA_RESULT";
  sender_subject_code: string;
  body: string;
  sent_at: string;
  photo?: { photo_id: string; mode: "ONCE" | "KEEP"; viewed_at: string | null; expired: boolean; image_url: string | null };
  insta?: {
    status: string;
    requester_code: string;
    requester_handle: string;
    responder_code: string;
    responder_handle: string | null;
    responded_at: string | null;
  };
};

const INSTA_STATUS_LABEL: Record<string, string> = { PENDING: "답 기다리는 중", ACCEPTED: "교환됨", DECLINED: "거절됨", CANCELLED: "요청 취소" };
type Chat = {
  match_id: string;
  status: string;
  matched_at: string;
  ended_at: string | null;
  members: [Member, Member];
  messages: Msg[];
  has_more: boolean;
};

const MATCH_STATUS_LABEL: Record<string, string> = { ACTIVE: "대화 중", UNMATCHED: "매칭 해제", BLOCKED: "차단으로 종료", HIDDEN: "숨김 (예전 매칭 정지)" };

/** 관리자 대화 열람 (읽기 전용). 열 때마다 감사 로그에 CHAT_VIEW가 남는다. */
export default function ChatViewer() {
  const { matchId } = useParams<{ matchId: string }>();
  const admin = useAdmin();
  const [chat, setChat] = useState<Chat | null>(null);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(
    () =>
      adminApi<Chat>(`/matches/${matchId}/messages`)
        .then(setChat)
        .catch((e) => setError(errorMessage(e))),
    [matchId],
  );

  useEffect(() => {
    load();
  }, [load]);

  async function loadOlder() {
    if (!chat || chat.messages.length === 0) return;
    setLoadingMore(true);
    try {
      const older = await adminApi<Chat>(`/matches/${matchId}/messages?before=${chat.messages[0].message_id}`);
      setChat({ ...chat, messages: [...older.messages, ...chat.messages], has_more: older.has_more });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoadingMore(false);
    }
  }

  if (!admin.can("chats:read")) return <Notice tone="error">대화 열람 권한이 없습니다.</Notice>;
  if (!chat) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  const [left, right] = chat.members;
  const label = (m: Member) => `${m.subject_code}${m.nickname ? ` · ${m.nickname}` : " · (탈퇴)"}`;

  return (
    <>
      <button onClick={() => history.back()} className="text-[13px] text-ink-soft hover:text-ink">
        ← 뒤로
      </button>
      <div className="mb-6 mt-3">
        <h1 className="text-[22px] font-semibold">대화 열람</h1>
        <p className="mt-1 text-[13px] text-ink-faint">
          {dateTime(chat.matched_at)} 매칭 · {MATCH_STATUS_LABEL[chat.status] ?? chat.status}
          {chat.ended_at && <> ({dateTime(chat.ended_at)})</>}
        </p>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[14px]">
          {[left, right].map((m, i) => (
            <span key={m.user_id}>
              <span className={i === 0 ? "text-ink-soft" : "text-brick"}>{i === 0 ? "왼쪽" : "오른쪽"}</span>{" "}
              {admin.can("users:read") ? (
                <Link href={`/admin/users/${m.user_id}`} className="font-mono underline underline-offset-4">
                  {label(m)}
                </Link>
              ) : (
                <span className="font-mono">{label(m)}</span>
              )}
            </span>
          ))}
        </div>
      </div>

      <Notice>이 화면을 연 기록(누가·언제·어느 대화)은 감사 로그에 남아요.</Notice>

      <div className="mt-6 max-w-2xl space-y-3 rounded-card border border-line bg-paper-card p-5">
        {chat.has_more && (
          <div className="text-center">
            <Button size="sm" variant="secondary" loading={loadingMore} onClick={loadOlder}>
              이전 메시지 더 보기
            </Button>
          </div>
        )}
        {chat.messages.length === 0 && <p className="py-8 text-center text-[14px] text-ink-faint">주고받은 메시지가 없어요.</p>}
        {chat.messages.map((m) => {
          const mine = m.sender_subject_code === right.subject_code;
          return (
            <div key={m.message_id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] ${mine ? "text-right" : ""}`}>
                {m.photo ? (
                  <div className="inline-block rounded-lg border border-line bg-paper p-2 text-left">
                    <p className="mb-1.5 text-[12px] text-ink-soft">
                      {m.photo.mode === "ONCE" ? "1회용 사진" : "보관 사진"}
                      {m.photo.mode === "ONCE" && (m.photo.viewed_at ? ` · ${dateTime(m.photo.viewed_at)}에 상대가 봄` : " · 아직 안 봄")}
                    </p>
                    {m.photo.image_url ? (
                      <a href={m.photo.image_url} target="_blank" rel="noreferrer">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={m.photo.image_url} alt="대화방 사진" className="max-h-64 max-w-full rounded-md" />
                      </a>
                    ) : (
                      <p className="text-[13px] text-ink-faint">보관 기간(90일)이 지나 파일이 지워졌어요.</p>
                    )}
                  </div>
                ) : m.insta ? (
                  <div className="inline-block rounded-lg border border-line bg-paper px-3.5 py-2.5 text-left text-[13.5px] leading-relaxed">
                    <p className="font-semibold">
                      인스타 아이디 교환 요청 · {INSTA_STATUS_LABEL[m.insta.status] ?? m.insta.status}
                    </p>
                    <p>
                      요청 <span className="font-mono">{m.insta.requester_code}</span> : <b>@{m.insta.requester_handle}</b>
                    </p>
                    <p>
                      상대 <span className="font-mono">{m.insta.responder_code}</span> :{" "}
                      {m.insta.responder_handle ? <b>@{m.insta.responder_handle}</b> : <span className="text-ink-faint">(적지 않음)</span>}
                    </p>
                  </div>
                ) : (
                  <p
                    className={`inline-block whitespace-pre-wrap break-words rounded-lg px-3.5 py-2 text-left text-[14.5px] leading-relaxed ${
                      m.type === "INSTA_RESULT" ? "bg-paper-deep text-ink-soft" : mine ? "bg-ink text-paper" : "border border-line bg-paper"
                    }`}
                  >
                    {m.body}
                  </p>
                )}
                <p className="mt-1 text-[11.5px] text-ink-faint">
                  <span className="font-mono">{m.sender_subject_code}</span> · {dateTime(m.sent_at)}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
