"use client";

import { useState } from "react";
import { Button, Field, Modal, Notice, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/format";
import { REPORT_REASONS } from "@/lib/types";

/**
 * 신고 창. 대화방(matchId) 기준으로 신고한다.
 * → 대화가 끝났거나 상대가 탈퇴해서 프로필이 없어도 신고할 수 있다.
 */
export function ReportModal({ open, onClose, matchId, onDone }: { open: boolean; onClose: () => void; matchId: string; onDone?: () => void }) {
  const [reason, setReason] = useState("");
  const [desc, setDesc] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      await api("/reports", { method: "POST", body: { match_id: matchId, reason, description: desc || null } });
      setDone(true);
      onDone?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="신고하기">
      {done ? (
        <div className="space-y-4">
          <Notice tone="ok">신고가 접수됐어요. 운영진이 대화 내용을 확인한 뒤 알림으로 결과를 알려드릴게요.</Notice>
          <Button variant="secondary" className="w-full" onClick={onClose}>
            닫기
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2">
            {REPORT_REASONS.map((r) => (
              <button
                key={r.value}
                type="button"
                onClick={() => setReason(r.value)}
                className={cn("rounded-md border px-3 py-2.5 text-left text-[14px]", reason === r.value ? "border-ink bg-ink text-paper" : "border-line bg-paper-card hover:border-line-strong")}
              >
                {r.label}
              </button>
            ))}
          </div>
          <Field label="자세한 내용 (선택)">
            <Textarea value={desc} maxLength={1000} onChange={(e) => setDesc(e.target.value)} rows={3} />
          </Field>
          {error && <Notice tone="error">{error}</Notice>}
          <Button variant="danger" className="w-full" disabled={!reason} loading={loading} onClick={submit}>
            신고 접수
          </Button>
        </div>
      )}
    </Modal>
  );
}
