"use client";

import { useRef, useState } from "react";
import { Button, Notice } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";

/** 사진 제출. 미리보기는 본인 브라우저 안에서만 보이고, 서버에는 비공개로 저장된다. */
export function PhotoUpload({ onUploaded, submitLabel = "검수 요청하기" }: { onUploaded?: () => void; submitLabel?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string>("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function pick(f: File | undefined) {
    setError("");
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) return setError("jpg, png, webp 사진만 올릴 수 있어요.");
    if (f.size > 5 * 1024 * 1024) return setError("5MB 이하 사진만 올릴 수 있어요.");
    setFile(f);
    setPreview(URL.createObjectURL(f));
  }

  async function upload() {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
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
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="group relative flex aspect-[4/5] w-full items-center justify-center overflow-hidden rounded-card border border-dashed border-line-strong bg-paper-card transition-colors hover:border-ink"
      >
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="선택한 사진 미리보기" className="h-full w-full object-cover" />
        ) : (
          <span className="text-center">
            <span className="block text-[15px] font-medium text-ink">사진 선택</span>
            <span className="mt-1 block text-[13px] text-ink-faint">얼굴이 잘 보이는 최근 사진 한 장</span>
          </span>
        )}
      </button>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />

      <ul className="space-y-1.5 text-[13px] leading-relaxed text-ink-soft">
        <li>— 사진은 운영진만 확인하고, 다른 학생에게는 절대 보이지 않아요.</li>
        <li>— 위치 정보 등 사진 속 메타데이터는 저장할 때 지워져요.</li>
        <li>— 검수가 끝나면 네 가지 항목의 평가가 프로필에 표시돼요.</li>
      </ul>

      {error && <Notice tone="error">{error}</Notice>}
      <Button type="button" size="lg" className="w-full" disabled={!file} loading={loading} onClick={upload}>
        {submitLabel}
      </Button>
    </div>
  );
}
