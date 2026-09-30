"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";

const MAX_PHOTOS = 3;
const MAX_SIDE = 2048; // 서버도 긴 변을 2048px로 줄인다 → 미리 줄여서 보내면 업로드가 빠르다
const MAX_BYTES = 10 * 1024 * 1024; // 서버 한 장 제한과 같게

type Picked = { id: string; file: File; preview: string };

/** 사진 제출 (최대 3장). 미리보기는 본인 브라우저 안에서만 보이고, 서버에는 비공개로 저장된다.
 *
 *  사진 형식 문제(2026-09-30):
 *  - 휴대폰 카메라 JPEG(MPO), 윈도우 .jfif, MIME이 image/jpg·빈 값인 사진이 거절되던 문제가 있었다.
 *  - 그래서 브라우저에서 먼저 일반 JPEG로 다시 그려서(압축) 보낸다 → 형식·용량 문제가 거의 사라진다.
 *  - 브라우저가 못 여는 사진이면 원본을 그대로 보내고, 서버가 내용으로 다시 확인한다.
 */
export function PhotoUpload({ onUploaded, submitLabel = "검수 요청하기" }: { onUploaded?: () => void; submitLabel?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Picked[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [preparing, setPreparing] = useState(false);

  // 화면을 떠날 때 미리보기 주소 정리 (메모리)
  const pickedRef = useRef(picked);
  useEffect(() => {
    pickedRef.current = picked;
  }, [picked]);
  useEffect(() => () => pickedRef.current.forEach((p) => URL.revokeObjectURL(p.preview)), []);

  async function pick(list: FileList | null) {
    setError("");
    if (!list || list.length === 0) return;
    const room = MAX_PHOTOS - picked.length;
    const files = Array.from(list).slice(0, room);
    if (list.length > room) setError(`사진은 최대 ${MAX_PHOTOS}장까지 올릴 수 있어요.`);
    setPreparing(true);
    const next: Picked[] = [];
    for (const f of files) {
      // 이미지가 아닌 파일(문서 등)만 막는다. 형식은 서버가 내용으로 확인한다.
      if (f.type && !f.type.startsWith("image/")) {
        setError("사진 파일만 올릴 수 있어요.");
        continue;
      }
      const file = await toJpeg(f);
      if (file.size > MAX_BYTES) {
        setError("10MB 이하 사진만 올릴 수 있어요.");
        continue;
      }
      next.push({ id: `${Date.now()}-${Math.random()}`, file, preview: URL.createObjectURL(file) });
    }
    setPreparing(false);
    setPicked((prev) => [...prev, ...next].slice(0, MAX_PHOTOS));
    if (input.current) input.current.value = ""; // 같은 사진을 지웠다가 다시 고를 수 있게
  }

  function remove(id: string) {
    setPicked((prev) => {
      const gone = prev.find((p) => p.id === id);
      if (gone) URL.revokeObjectURL(gone.preview);
      return prev.filter((p) => p.id !== id);
    });
  }

  async function upload() {
    if (picked.length === 0) return;
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      picked.forEach((p) => form.append("files", p.file));
      await api("/me/photos", { method: "POST", form });
      onUploaded?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-3 gap-2.5">
        {picked.map((p, i) => (
          <div key={p.id} className="relative aspect-[4/5] overflow-hidden rounded-card border border-line bg-paper-card">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={p.preview} alt={`선택한 사진 ${i + 1}`} className="h-full w-full object-cover" />
            {i === 0 && <span className="absolute left-1.5 top-1.5 rounded-sm bg-ink/80 px-1.5 py-0.5 text-[11px] text-paper">대표</span>}
            <button
              type="button"
              onClick={() => remove(p.id)}
              aria-label={`사진 ${i + 1} 빼기`}
              className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-ink/70 text-[15px] leading-none text-paper hover:bg-ink"
            >
              ×
            </button>
          </div>
        ))}
        {picked.length < MAX_PHOTOS && (
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={preparing}
            className={cn(
              "flex aspect-[4/5] items-center justify-center rounded-card border border-dashed border-line-strong bg-paper-card text-center transition-colors hover:border-ink",
              picked.length === 0 && "col-span-3 aspect-[16/9] sm:aspect-[2/1]",
            )}
          >
            <span>
              <span className="block text-[22px] leading-none text-ink-faint">+</span>
              <span className="mt-1.5 block text-[14px] font-medium text-ink">{preparing ? "사진 준비 중…" : "사진 추가"}</span>
              <span className="mt-0.5 block text-[12px] text-ink-faint">
                <span className="num">{picked.length}</span>/<span className="num">{MAX_PHOTOS}</span>
              </span>
            </span>
          </button>
        )}
      </div>
      <input ref={input} type="file" accept="image/*" multiple className="hidden" onChange={(e) => pick(e.target.files)} />

      <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink-soft">
        <li>— 얼굴이 잘 보이는 최근 사진을 1~3장 골라주세요. AI가 함께 보고 한 번에 평가해요.</li>
        <li>— 사진은 AI가 평가하고, 다른 학생에게는 절대 보이지 않아요.</li>
        <li>— 위치 정보 등 사진 속 메타데이터는 저장할 때 지워져요.</li>
        <li>— 평가가 끝나면 네 가지 항목의 점수가 프로필에 표시돼요.</li>
      </ul>

      {error && <Notice tone="error">{error}</Notice>}
      <Button type="button" size="lg" className="w-full" disabled={picked.length === 0 || preparing} loading={loading} onClick={upload}>
        {picked.length > 1 ? `사진 ${picked.length}장 ${submitLabel}` : submitLabel}
      </Button>
    </div>
  );
}

/** 브라우저에서 사진을 일반 JPEG로 다시 그린다 (긴 변 2048px, 회전 보정).
 *  브라우저가 열지 못하는 사진이면 원본을 그대로 돌려준다. */
async function toJpeg(file: File): Promise<File> {
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const ratio = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const w = Math.max(1, Math.round(bitmap.width * ratio));
    const h = Math.max(1, Math.round(bitmap.height * ratio));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return file;
    ctx.fillStyle = "#ffffff"; // 투명한 PNG는 흰 배경으로
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (!blob) return file;
    const name = (file.name.replace(/\.[^.]*$/, "") || "photo") + ".jpg";
    return new File([blob], name, { type: "image/jpeg" });
  } catch {
    return file;
  }
}
