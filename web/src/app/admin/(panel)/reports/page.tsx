"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button, Notice, PageTitle, Spinner, Textarea } from "@/components/ui";
import { REPORT_STATUS_LABEL, adminApi, useAdmin } from "@/lib/admin";
import { errorMessage } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { REPORT_REASONS } from "@/lib/types";

type Report = {
  report_id: string;
  reporter_user_id: string;
  reported_user_id: string;
  match_id: string | null;
  reason: string;
  description: string | null;
  status: string;
  admin_note: string | null;
  created_at: string;
};

const REASON_LABEL = Object.fromEntries(REPORT_REASONS.map((r) => [r.value, r.label]));
const TABS = ["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"];

export default function ReportsPage() {
  const [status, setStatus] = useState("OPEN");
  const [items, setItems] = useState<Report[] | null>(null);

  const load = useCallback(() => {
    setItems(null);
    adminApi<{ reports: Report[] }>(`/reports?status=${status}`).then((r) => setItems(r.reports));
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageTitle eyebrow="신고" title="신고 처리" desc="계정 제재가 필요하면 신고 대상자의 사용자 화면에서 상태를 바꿔주세요." />
      <div className="mb-6 flex gap-6 border-b border-line text-[14px]">
        {TABS.map((t) => (
          <button key={t} onClick={() => setStatus(t)} className={status === t ? "-mb-px border-b-2 border-ink pb-3 font-semibold" : "pb-3 text-ink-faint hover:text-ink"}>
            {REPORT_STATUS_LABEL[t]}
          </button>
        ))}
      </div>
      {!items ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="py-12 text-center text-[14px] text-ink-faint">처리할 신고가 없어요.</p>
      ) : (
        <div className="space-y-3">
          {items.map((r) => (
            <ReportRow key={r.report_id} report={r} onChanged={load} />
          ))}
        </div>
      )}
    </>
  );
}

function ReportRow({ report, onChanged }: { report: Report; onChanged: () => void }) {
  const admin = useAdmin();
  const [note, setNote] = useState(report.admin_note ?? "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const closed = report.status === "RESOLVED" || report.status === "DISMISSED";

  async function update(status: string) {
    setBusy(true);
    setError("");
    try {
      await adminApi(`/reports/${report.report_id}`, { method: "PATCH", body: { status, admin_note: note || null } });
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <article className="rounded-card border border-line bg-paper-card p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[15px] font-semibold">{REASON_LABEL[report.reason] ?? report.reason}</p>
        <p className="text-[12.5px] text-ink-faint">{dateTime(report.created_at)}</p>
      </div>
      {report.description && <p className="mt-2 whitespace-pre-line text-[14px] leading-relaxed text-ink">{report.description}</p>}
      <p className="mt-3 text-[12.5px] text-ink-faint">
        신고 대상{" "}
        {admin.can("users:read") ? (
          <Link href={`/admin/users/${report.reported_user_id}`} className="font-mono text-ink underline underline-offset-4">
            {report.reported_user_id.slice(0, 8)}
          </Link>
        ) : (
          <span className="font-mono">{report.reported_user_id.slice(0, 8)}</span>
        )}
        {report.match_id &&
          (admin.can("chats:read") ? (
            <>
              {" · "}
              <Link href={`/admin/chats/${report.match_id}`} className="text-ink underline underline-offset-4">
                신고된 대화 보기
              </Link>
            </>
          ) : (
            " · 대화 중 신고"
          ))}
      </p>

      {admin.can("reports:update") && (
        <div className="mt-4 space-y-3 border-t border-line pt-4">
          <Textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="처리 메모 (운영진 전용)" className="min-h-[64px]" />
          {error && <Notice tone="error">{error}</Notice>}
          <div className="flex flex-wrap gap-2">
            {report.status === "OPEN" && (
              <Button size="sm" variant="secondary" loading={busy} onClick={() => update("IN_REVIEW")}>
                검토 시작
              </Button>
            )}
            {!closed && (
              <>
                <Button size="sm" loading={busy} onClick={() => update("RESOLVED")}>
                  처리 완료
                </Button>
                <Button size="sm" variant="ghost" loading={busy} onClick={() => update("DISMISSED")}>
                  기각
                </Button>
              </>
            )}
            {closed && (
              <Button size="sm" variant="secondary" loading={busy} onClick={() => update(report.status)}>
                메모 저장
              </Button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
