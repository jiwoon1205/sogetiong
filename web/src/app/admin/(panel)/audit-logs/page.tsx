"use client";

import { useEffect, useState } from "react";
import { PageTitle, Spinner } from "@/components/ui";
import { adminApi } from "@/lib/admin";
import { dateTime } from "@/lib/format";

type Log = { admin_id: string | null; action: string; target_type: string; target_id: string | null; ip: string | null; metadata: Record<string, unknown> | null; created_at: string };

const ACTION_LABEL: Record<string, string> = {
  ADMIN_LOGIN: "관리자 로그인",
  PHOTO_VIEW: "사진 열람",
  PHOTO_REJECT: "사진 반려",
  EVALUATION_CREATE: "외적 평가 생성",
  EVALUATION_UPDATE: "외적 평가 수정",
  USER_VIEW: "사용자 조회",
  USER_PRIVATE_VIEW: "개인정보 열람",
  USER_STATUS_CHANGE: "계정 상태 변경",
  REPORT_UPDATE: "신고 처리",
  CHAT_VIEW: "대화 열람",
  MATCH_SUSPEND: "매칭 정지",
  MATCH_AUTO_SUSPEND: "자동 매칭 정지 (하루 매칭 한도)",
  MATCH_UNSUSPEND: "매칭 정지 풀기",
  MATCH_REVEAL: "숨김 매칭 공개",
};

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<Log[] | null>(null);

  useEffect(() => {
    adminApi<{ logs: Log[] }>("/audit-logs?limit=200").then((r) => setLogs(r.logs));
  }, []);

  return (
    <>
      <PageTitle eyebrow="감사 로그" title="운영진 활동 기록" desc="최근 200건. 기록은 수정하거나 지울 수 없어요." />
      {!logs ? (
        <Spinner />
      ) : (
        <div className="overflow-x-auto rounded-card border border-line bg-paper-card">
          <table className="w-full min-w-[44rem] text-[13.5px]">
            <thead className="border-b border-line text-left text-[12.5px] text-ink-faint">
              <tr>
                <th className="px-5 py-3 font-normal">일시</th>
                <th className="px-5 py-3 font-normal">행위</th>
                <th className="px-5 py-3 font-normal">대상</th>
                <th className="px-5 py-3 font-normal">관리자</th>
                <th className="px-5 py-3 font-normal">세부</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {logs.map((l, i) => (
                <tr key={i}>
                  <td className="num whitespace-nowrap px-5 py-3 text-ink-soft">{dateTime(l.created_at)}</td>
                  <td className={`px-5 py-3 ${l.action === "USER_PRIVATE_VIEW" || l.action === "CHAT_VIEW" ? "font-semibold text-brick" : ""}`}>{ACTION_LABEL[l.action] ?? l.action}</td>
                  <td className="px-5 py-3 font-mono text-[12.5px] text-ink-soft">
                    {l.target_type} {l.target_id?.slice(0, 8)}
                  </td>
                  <td className="px-5 py-3 font-mono text-[12.5px] text-ink-soft">{l.admin_id ? l.admin_id.slice(0, 8) : "자동"}</td>
                  <td className="max-w-[16rem] truncate px-5 py-3 font-mono text-[12px] text-ink-faint">{l.metadata ? JSON.stringify(l.metadata) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
