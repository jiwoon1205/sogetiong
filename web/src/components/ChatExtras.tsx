"use client";

/**
 * 대화방 ＋ 버튼: 사진 보내기 · 인스타 아이디 교환 (2026-11-14)
 * 규칙은 백엔드 app/services/chat_extra_service.py 맨 위 설명.
 *
 * - 훕팅은 웹사이트라 캡처를 막거나 캡처 사실을 알아낼 수 없다.
 *   그래서 1회용 사진은 5초만 보이고, 다른 앱으로 넘어가면 바로 닫히며, 사진에 보는 사람의 코드가 새겨진다(서버에서).
 */

import { useEffect, useRef, useState } from "react";
import { toJpeg } from "@/components/PhotoUpload";
import { Button, Checkbox, Input, Modal, Notice } from "@/components/ui";
import { ApiError, errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";
import type { ChatMessage, ChatPhoto, InstaShare } from "@/lib/types";

const CHAT_PHOTO_MAX_SIDE = 1600;
// 인스타그램 아이디 규칙 (서버와 같음): 영문 소문자·숫자·마침표·밑줄 1~30자, 마침표로 끝나거나 두 개 연속은 안 됨
const HANDLE_RE = /^(?!.*\.\.)(?!.*\.$)[a-z0-9._]{1,30}$/;

export function normalizeHandle(raw: string): string {
  return raw.trim().replace(/^@+/, "").trim().toLowerCase();
}

function csrf(): string | undefined {
  const m = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : undefined;
}

/** 사진 올리기 (FormData). 서버가 돌려준 메시지를 그대로 돌려준다 */
async function postPhoto(matchId: string, file: File, mode: "ONCE" | "KEEP"): Promise<ChatMessage> {
  const form = new FormData();
  form.append("file", file);
  form.append("mode", mode);
  const token = csrf();
  const res = await fetch(`/api/v1/matches/${matchId}/photos`, {
    method: "POST",
    body: form,
    credentials: "include",
    headers: token ? { "X-CSRF-Token": token } : {},
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && typeof data.detail === "string" ? data.detail : "사진을 보내지 못했어요.";
    throw new ApiError(res.status, detail, /^[A-Z_]+$/.test(detail) ? detail : String(res.status));
  }
  return data as ChatMessage;
}

/** 1회용 사진 열기 → 사진 데이터(Blob). 한 번 열면 서버가 "봤음"으로 기록해 다시는 안 열린다 */
async function openOncePhoto(matchId: string, photoId: string): Promise<Blob> {
  const token = csrf();
  const res = await fetch(`/api/v1/matches/${matchId}/photos/${photoId}/open`, {
    method: "POST",
    credentials: "include",
    cache: "no-store",
    headers: token ? { "X-CSRF-Token": token } : {},
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new ApiError(res.status, data && typeof data.detail === "string" ? data.detail : "사진을 열지 못했어요.", String(res.status));
  }
  return res.blob();
}

// ---------- ＋ 메뉴 ----------

export function PlusMenu({
  open,
  onClose,
  onPhoto,
  onInsta,
  instaBlocked,
}: {
  open: boolean;
  onClose: () => void;
  onPhoto: () => void;
  onInsta: () => void;
  /** 인스타 요청을 지금 못 하는 이유 (진행 중·이미 교환). 없으면 null */
  instaBlocked: string | null;
}) {
  return (
    <Modal open={open} onClose={onClose} title="보내기">
      <div className="grid grid-cols-2 gap-3">
        <MenuButton title="사진 보내기" desc="1회 보기 또는 대화에 보관" onClick={onPhoto} icon="photo" />
        <MenuButton
          title="인스타 아이디 교환"
          desc={instaBlocked ?? "서로 수락하면 동시에 공개"}
          onClick={onInsta}
          icon="insta"
          disabled={instaBlocked !== null}
        />
      </div>
    </Modal>
  );
}

function MenuButton({
  title,
  desc,
  onClick,
  icon,
  disabled,
}: {
  title: string;
  desc: string;
  onClick: () => void;
  icon: "photo" | "insta";
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex flex-col items-center gap-2 rounded-card border border-line bg-paper-card px-3 py-5 text-center transition-colors hover:border-line-strong disabled:opacity-45"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-paper-deep text-ink">
        {icon === "photo" ? (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
            <rect x="3" y="5" width="18" height="14" rx="2.5" />
            <circle cx="9" cy="10" r="1.6" />
            <path d="M4 17l5-4.5 4 3.5 3-2.5 4 3.5" strokeLinejoin="round" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden>
            <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
            <circle cx="12" cy="12" r="4" />
            <circle cx="17.2" cy="6.8" r="0.9" fill="currentColor" stroke="none" />
          </svg>
        )}
      </span>
      <span className="text-[14.5px] font-semibold text-ink">{title}</span>
      <span className="text-[12px] leading-snug text-ink-faint">{desc}</span>
    </button>
  );
}

// ---------- 사진 보내기 ----------

type PhotoSendProps = { open: boolean; onClose: () => void; matchId: string; onSent: (m: ChatMessage) => void };

/** 열 때마다 새로 그려서(고른 사진·방식이 처음 상태로) 시작한다 */
export function PhotoSendModal(props: PhotoSendProps) {
  return props.open ? <PhotoSendInner {...props} /> : null;
}

function PhotoSendInner({ open, onClose, matchId, onSent }: PhotoSendProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [mode, setMode] = useState<"ONCE" | "KEEP">("ONCE");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);

  // 미리보기 주소는 다른 사진을 고르거나 창을 닫을 때 정리한다
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  async function pick(list: FileList | null) {
    const f = list?.[0];
    if (!f) return;
    setError("");
    const jpeg = await toJpeg(f, CHAT_PHOTO_MAX_SIDE);
    setFile(jpeg);
    setPreview(URL.createObjectURL(jpeg));
  }

  async function send() {
    if (!file) return;
    setSending(true);
    setError("");
    try {
      onSent(await postPhoto(matchId, file, mode));
      onClose();
    } catch (err) {
      setError(err instanceof ApiError && err.code === "SUPER_LIKE_WAIT_REPLY" ? "상대가 답장하면 이어서 보낼 수 있어요." : errorMessage(err));
      setSending(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="사진 보내기">
      <div className="space-y-5">
        <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files)} />
        {preview ? (
          <button type="button" onClick={() => fileRef.current?.click()} className="block w-full" aria-label="다른 사진 고르기">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={preview} alt="보낼 사진" className="mx-auto max-h-60 rounded-card object-contain" />
            <span className="mt-2 block text-center text-[12.5px] text-ink-faint underline underline-offset-4">다른 사진 고르기</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="flex h-36 w-full flex-col items-center justify-center gap-1 rounded-card border border-dashed border-line-strong bg-paper-card text-[14px] text-ink-soft hover:border-ink-soft"
          >
            <span className="text-[22px] leading-none">＋</span>
            사진 고르기
          </button>
        )}

        <div className="space-y-2">
          <ModeOption
            active={mode === "ONCE"}
            onClick={() => setMode("ONCE")}
            title="1회 보기"
            desc="상대가 ‘사진 보기’를 눌러야 열리고, 5초 뒤 사라져요. 한 번 보면 다시 볼 수 없어요."
          />
          <ModeOption
            active={mode === "KEEP"}
            onClick={() => setMode("KEEP")}
            title="대화에 보관"
            desc="일반 사진처럼 대화방에 계속 남아요."
          />
        </div>

        <p className="rounded-md bg-paper-deep px-3.5 py-3 text-[12.5px] leading-relaxed text-ink-soft">
          웹사이트 특성상 <b className="font-semibold text-ink">캡처를 완전히 막을 수는 없어요.</b> 1회용 사진에는 보는 사람의 사용자 코드가
          흐리게 새겨져서, 캡처가 퍼지면 누가 유출했는지 알 수 있어요. 보낸 사진은 신고 처리를 위해 운영진이 90일 동안 확인할 수 있어요.
        </p>

        {error && <Notice tone="error">{error}</Notice>}
        <Button className="w-full" size="lg" disabled={!file} loading={sending} onClick={send}>
          {mode === "ONCE" ? "1회용 사진 보내기" : "사진 보내기"}
        </Button>
      </div>
    </Modal>
  );
}

function ModeOption({ active, onClick, title, desc }: { active: boolean; onClick: () => void; title: string; desc: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 rounded-md border px-3.5 py-3 text-left transition-colors",
        active ? "border-ink bg-paper-card" : "border-line bg-paper-card hover:border-line-strong",
      )}
    >
      <span className={cn("mt-1 h-4 w-4 shrink-0 rounded-full border", active ? "border-[5px] border-ink" : "border-line-strong")} />
      <span>
        <span className="block text-[14.5px] font-semibold text-ink">{title}</span>
        <span className="mt-0.5 block text-[12.5px] leading-relaxed text-ink-soft">{desc}</span>
      </span>
    </button>
  );
}

// ---------- 대화창 안의 사진 ----------

export function PhotoBubble({
  matchId,
  message,
  photo,
  onOpened,
  onZoom,
}: {
  matchId: string;
  message: ChatMessage;
  photo: ChatPhoto;
  /** 1회용 사진을 열었을 때 (사진 데이터 주소) */
  onOpened: (url: string, photoId: string) => void;
  onZoom: (url: string) => void;
}) {
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  const mine = message.is_mine;
  const pill = cn(
    "flex items-center gap-2 rounded-2xl px-4 py-2.5 text-[14px]",
    mine ? "rounded-br-md bg-ink text-paper" : "rounded-bl-md border border-line bg-paper-card text-ink",
  );

  if (photo.state === "AVAILABLE" && photo.image_url) {
    const ratio = photo.width && photo.height ? photo.width / photo.height : 1;
    return (
      <button type="button" onClick={() => onZoom(photo.image_url!)} className="block max-w-[62%]" aria-label="사진 크게 보기">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={photo.image_url}
          alt="보낸 사진"
          loading="lazy"
          draggable={false}
          onContextMenu={(e) => e.preventDefault()}
          style={{ aspectRatio: String(ratio) }}
          className={cn("w-56 max-w-full select-none rounded-2xl border border-line bg-paper-deep object-cover", mine ? "rounded-br-md" : "rounded-bl-md")}
        />
      </button>
    );
  }

  if (photo.state === "UNOPENED") {
    async function open() {
      setOpening(true);
      setError("");
      try {
        const blob = await openOncePhoto(matchId, photo.photo_id);
        onOpened(URL.createObjectURL(blob), photo.photo_id);
      } catch (err) {
        setError(errorMessage(err));
        if (err instanceof ApiError && err.status === 410) onOpened("", photo.photo_id); // 이미 봤음 → 상태만 바꿈
      } finally {
        setOpening(false);
      }
    }
    return (
      <div>
        <button type="button" onClick={open} disabled={opening} className={cn(pill, "font-semibold")}>
          <OnceIcon />
          {opening ? "여는 중…" : "1회용 사진 · 사진 보기"}
        </button>
        {error && <p className="mt-1 text-[12px] text-brick">{error}</p>}
      </div>
    );
  }

  const label =
    photo.state === "EXPIRED"
      ? "보관 기간이 지난 사진"
      : photo.state === "OPENED"
        ? "열어본 1회용 사진"
        : photo.state === "SENT_OPENED"
          ? "1회용 사진 · 상대가 봤어요"
          : "1회용 사진 · 아직 안 봤어요";
  return (
    <p className={cn(pill, "opacity-70")}>
      <OnceIcon />
      {label}
    </p>
  );
}

function OnceIcon() {
  return (
    <svg viewBox="0 0 16 16" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
      <circle cx="8" cy="8" r="6.2" strokeDasharray="2.6 1.6" />
      <path d="M7 5.8L8.4 5v6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** 1회용 사진 보기 화면: seconds초 동안만, 다른 앱으로 넘어가면 바로 닫힘. 길게 눌러 저장·드래그 막기 */
export function OnceViewer({ url, seconds, onClose }: { url: string; seconds: number; onClose: () => void }) {
  const [left, setLeft] = useState(seconds);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      const remain = seconds - Math.floor((Date.now() - started) / 1000);
      if (remain <= 0) closeRef.current();
      else setLeft(remain);
    }, 200);
    const hide = () => closeRef.current();
    const onVisibility = () => {
      if (document.hidden) hide();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", hide);
    window.addEventListener("pagehide", hide);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", hide);
      window.removeEventListener("pagehide", hide);
    };
  }, [seconds]);

  return (
    <div
      className="fixed inset-0 z-[60] flex select-none flex-col bg-black"
      style={{ WebkitTouchCallout: "none", WebkitUserSelect: "none" }}
      onContextMenu={(e) => e.preventDefault()}
      onClick={onClose}
    >
      <div className="flex items-center justify-between px-5 pb-3 pt-[max(1rem,env(safe-area-inset-top))] text-[13px] text-white/80">
        <span>1회용 사진</span>
        <span className="num rounded-full bg-white/15 px-3 py-1 text-white">{left}초</span>
      </div>
      {/* <img> 대신 배경 그림으로 띄워 길게 눌러 "이미지 저장"이 뜨지 않게 한다 */}
      <div
        className="min-h-0 flex-1 bg-contain bg-center bg-no-repeat"
        style={{ backgroundImage: `url(${url})` }}
        role="img"
        aria-label="1회용 사진"
      />
      <p className="px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 text-center text-[12px] leading-relaxed text-white/60">
        사진에 내 사용자 코드가 새겨져 있어요. 캡처해서 퍼뜨리면 누가 유출했는지 알 수 있어요.
        <br />
        화면을 누르면 닫혀요. 닫으면 다시 볼 수 없어요.
      </p>
    </div>
  );
}

/** 보관 사진 크게 보기 */
export function PhotoZoom({ url, onClose }: { url: string; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4" onClick={onClose} onContextMenu={(e) => e.preventDefault()}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="사진" draggable={false} className="max-h-full max-w-full select-none object-contain" />
    </div>
  );
}

// ---------- 인스타 아이디 교환 ----------

/** 아이디 적는 창 (요청할 때·수락할 때 같이 씀). 가짜·오타 아이디는 영구정지에 동의해야 보낼 수 있다 */
type InstaHandleProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  submitLabel: string;
  defaultHandle: string | null;
  onSubmit: (handle: string) => Promise<void>;
};

/** 열 때마다 새로 그려서(지난번 아이디를 미리 채우고, 동의는 다시 받기) 시작한다 */
export function InstaHandleModal(props: InstaHandleProps) {
  return props.open ? <InstaHandleInner {...props} /> : null;
}

function InstaHandleInner({ open, onClose, title, submitLabel, defaultHandle, onSubmit }: InstaHandleProps) {
  const [handle, setHandle] = useState(defaultHandle ?? "");
  const [agree, setAgree] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const clean = normalizeHandle(handle);
  const valid = HANDLE_RE.test(clean);

  async function submit() {
    if (!valid) {
      setError("인스타 아이디는 영문·숫자·마침표(.)·밑줄(_)로 된 30자 이하만 적을 수 있어요.");
      return;
    }
    if (!agree) {
      setError("아래 안내에 동의해야 보낼 수 있어요.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await onSubmit(clean);
      onClose();
    } catch (err) {
      setError(err instanceof ApiError && err.code === "SUPER_LIKE_WAIT_REPLY" ? "상대가 답장하면 이어서 보낼 수 있어요." : errorMessage(err));
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="space-y-5">
        <div className="rounded-md border border-brick/30 bg-brick-wash px-4 py-3 text-[13px] leading-relaxed text-brick-deep">
          <b className="font-semibold">가짜 아이디나 오타가 있는 아이디를 적으면 영구정지돼요.</b>
          <br />
          상대가 신고하면 운영진이 확인해요. 보내기 전에 아이디를 꼭 다시 확인해 주세요.
        </div>
        <label className="block">
          <span className="mb-1.5 block text-[13px] font-medium text-ink-soft">내 인스타 아이디</span>
          <div className="flex items-center gap-1 rounded-md border border-line bg-paper-card pl-3 focus-within:border-ink-soft">
            <span className="text-[16px] text-ink-faint">@</span>
            <Input
              value={handle}
              onChange={(e) => {
                setHandle(e.target.value);
                setError("");
              }}
              maxLength={40}
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              placeholder="instagram_id"
              aria-label="내 인스타 아이디"
              className="border-0 bg-transparent pl-0 focus:border-0"
            />
          </div>
          {handle && valid && (
            <span className="mt-1.5 block text-[12.5px] text-ink-faint">
              상대에게 <b className="font-semibold text-ink">@{clean}</b> 로 보여요.
            </span>
          )}
        </label>
        <Checkbox
          checked={agree}
          onChange={(v) => {
            setAgree(v);
            setError("");
          }}
        >
          <span className="text-[13.5px]">내 진짜 아이디가 맞아요. 가짜·오타 아이디면 영구정지되는 것에 동의해요.</span>
        </Checkbox>
        {error && <Notice tone="error">{error}</Notice>}
        <Button className="w-full" size="lg" disabled={!handle.trim()} loading={loading} onClick={submit}>
          {submitLabel}
        </Button>
      </div>
    </Modal>
  );
}

/** 대화창 안의 인스타 교환 카드 */
export function InstaCard({
  share,
  onAccept,
  onDecline,
  onCancel,
  onReport,
}: {
  share: InstaShare;
  onAccept: () => void;
  onDecline: () => Promise<void>;
  onCancel: () => Promise<void>;
  onReport: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const title =
    share.status === "ACCEPTED"
      ? "인스타 아이디를 교환했어요"
      : share.status === "DECLINED"
        ? "거절된 인스타 아이디 교환 요청"
        : share.status === "CANCELLED"
          ? "취소된 인스타 아이디 교환 요청"
          : share.requested_by_me
            ? "인스타 아이디 교환을 요청했어요"
            : "상대가 인스타 아이디 교환을 요청했어요";

  return (
    <div className="w-[80%] max-w-[19rem] rounded-card border border-line bg-paper-card px-4 py-3.5 text-[14px]">
      <p className="flex items-center gap-2 font-semibold text-ink">
        <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <rect x="3.5" y="3.5" width="17" height="17" rx="5" />
          <circle cx="12" cy="12" r="4" />
        </svg>
        {title}
      </p>

      {share.status === "ACCEPTED" && (
        <div className="mt-3 space-y-1.5">
          <HandleRow label="상대" handle={share.partner_handle} link />
          <HandleRow label="나" handle={share.my_handle} />
          <button type="button" onClick={onReport} className="pt-1 text-[12px] text-ink-faint underline underline-offset-4 hover:text-brick">
            상대 아이디가 가짜이거나 없는 계정인가요? 신고하기
          </button>
        </div>
      )}

      {share.status === "PENDING" && share.requested_by_me && (
        <div className="mt-2 space-y-2">
          <p className="text-[12.5px] leading-relaxed text-ink-soft">
            상대가 수락하면 서로의 아이디가 동시에 보여요. 그 전에는 내 아이디(@{share.my_handle})가 상대에게 보이지 않아요.
          </p>
          <button type="button" disabled={busy} onClick={() => run(onCancel)} className="text-[12.5px] text-ink-faint underline underline-offset-4 hover:text-ink">
            요청 취소
          </button>
        </div>
      )}

      {share.status === "PENDING" && !share.requested_by_me && (
        <div className="mt-2 space-y-3">
          <p className="text-[12.5px] leading-relaxed text-ink-soft">수락하려면 내 아이디를 적어야 해요. 수락하는 순간 서로의 아이디가 동시에 보여요.</p>
          <div className="flex gap-2">
            <Button size="sm" className="flex-1" disabled={busy} onClick={onAccept}>
              아이디 적고 수락
            </Button>
            <Button size="sm" variant="secondary" loading={busy} onClick={() => run(onDecline)}>
              거절
            </Button>
          </div>
        </div>
      )}

      {error && <p className="mt-2 text-[12px] text-brick">{error}</p>}
    </div>
  );
}

function HandleRow({ label, handle, link }: { label: string; handle: string | null; link?: boolean }) {
  if (!handle) return null;
  return (
    <p className="flex items-baseline gap-2">
      <span className="w-8 shrink-0 text-[12px] text-ink-faint">{label}</span>
      {link ? (
        <a
          href={`https://instagram.com/${encodeURIComponent(handle)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-ink underline underline-offset-4"
        >
          @{handle}
        </a>
      ) : (
        <span className="text-ink-soft">@{handle}</span>
      )}
    </p>
  );
}
