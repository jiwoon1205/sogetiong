"use client";

import { useState } from "react";
import { Button, Field, Modal, Notice, Textarea } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { BOARD_REPORT_REASONS } from "@/lib/board";
import { cn } from "@/lib/format";

export type BoardReportTarget = { type: "POST" | "COMMENT" | "PROFILE" | "NOTE"; id: string };

const TITLE = { POST: "글 신고", COMMENT: "댓글 신고", PROFILE: "프로필 신고", NOTE: "쪽지 신고" };

/** 게시판 신고 (2026-11-22). 같은 대상을 3명이 신고하면 자동으로 숨겨진다. */
export function BoardReportModal({ target, onClose, onDone }: { target: BoardReportTarget | null; onClose: () => void; onDone?: () => void }) {
  if (!target) return null;
  return <Inner key={`${target.type}-${target.id}`} target={target} onClose={onClose} onDone={onDone} />;
}

function Inner({ target, onClose, onDone }: { target: BoardReportTarget; onClose: () => void; onDone?: () => void }) {
  const [reason, setReason] = useState("");
  const [desc, setDesc] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    setError("");
    try {
      await api("/board/reports", { method: "POST", body: { target_type: target.type, target_id: target.id, reason, description: desc || null } });
      setDone(true);
      onDone?.();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={TITLE[target.type]}>
      {done ? (
        <div className="space-y-4">
          <Notice tone="ok">신고가 접수됐어요. 운영진이 확인하고 필요하면 바로 지우거나 게시판 이용을 정지해요.</Notice>
          <Button variant="secondary" className="w-full" onClick={onClose}>
            닫기
          </Button>
        </div>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2">
            {BOARD_REPORT_REASONS.map((r) => (
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
            <Textarea value={desc} maxLength={500} onChange={(e) => setDesc(e.target.value)} rows={3} />
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
