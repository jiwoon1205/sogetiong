"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ProfileCard } from "@/components/ProfileCard";
import { Button, Field, Input, Notice, Segmented, Select, Spinner } from "@/components/ui";
import { USER_STATUS_LABEL, adminApi, useAdmin } from "@/lib/admin";
import { api, errorMessage } from "@/lib/api";
import { dateTime, timeAgo } from "@/lib/format";
import { GENDER_LABEL, TIER_LABEL, TIER_OPTIONS, type AppearanceTier, type Card } from "@/lib/types";

type Gender = "MALE" | "FEMALE";
type WantGender = Gender | "ANY";

type Detail = {
  user_id: string;
  subject_code: string;
  status: string;
  created_at: string;
  last_active_at: string | null;
  is_beta_member?: boolean;
  signup_paid_at?: string | null;
  vip_until?: string | null;
  /** 이용권 (2026-10-04 구독제) */
  member_until?: string | null;
  member_days_banked?: number;
  membership_status?: "none" | "banked" | "active" | "expired";
  membership_free?: boolean;
  /** 무료 체험 좋아요 사용 개수 (2026-10-06) */
  trial_likes_used?: number;
  trial_like_limit?: number;
  /** 매칭 정지 (2026-10-05, 관리자만 봄) */
  match_suspended?: boolean;
  match_suspended_at?: string | null;
  hidden_matches?: number;
  profile: Card | null;
  campus: { id: string; name: string } | null;
  department: { id: string; name: string } | null;
  gender: Gender | null;
  preferred_gender: WantGender | null;
  /** 외모 등급 (내부 전용). null = 없음 → 추천에 나오지 않음 */
  appearance_tier: AppearanceTier | null;
  reports_received: number;
  deleted_at: string | null;
  /** 탈퇴한 사람의 예전 닉네임 (공개 프로필이 지워져도 남겨 둔 값) */
  deleted_nickname?: string | null;
  /** 탈퇴자의 프로필·사진이 지워지는(지워진) 시각 */
  data_purge_at?: string | null;
  photos?: { photo_id: string; review_status: string; uploaded_at: string | null; image_url: string }[];
  linked_accounts: { user_id: string; subject_code: string; status: string; created_at: string; deleted_at: string | null }[];
  private?: { email: string; real_name: string | null; phone_number: string | null; student_id: string | null; birth_date: string };
};

export default function UserDetail() {
  const { userId } = useParams<{ userId: string }>();
  const admin = useAdmin();
  const [d, setD] = useState<Detail | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(
    (includePrivate = false) =>
      adminApi<Detail>(`/users/${userId}${includePrivate ? "?include_private=true" : ""}`)
        .then(setD)
        .catch((e) => setError(errorMessage(e))),
    [userId],
  );

  useEffect(() => {
    load();
  }, [load]);

  if (!d) return error ? <Notice tone="error">{error}</Notice> : <Spinner />;

  return (
    <>
      <Link href="/admin/users" className="text-[13px] text-ink-soft hover:text-ink">
        ← 사용자 목록
      </Link>
      <div className="mb-8 mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="font-mono text-[26px] font-semibold tracking-wide">{d.subject_code}</h1>
        <p className="text-[13px] text-ink-faint">
          {dateTime(d.created_at)} 가입{d.deleted_at && <> · {dateTime(d.deleted_at)} 탈퇴</>} · 마지막 접속{" "}
          {d.last_active_at ? <span title={dateTime(d.last_active_at)}>{timeAgo(d.last_active_at)}</span> : "기록 없음"} · {USER_STATUS_LABEL[d.status] ?? d.status} · 받은 신고 <span className="num">{d.reports_received}</span>건
          {" · "}
          {d.is_beta_member ? "베타 가입" : "유료화 뒤 가입"}
          {" · "}
          {membershipLabel(d)}
          {d.trial_like_limit ? <> · 체험 좋아요 {d.trial_likes_used ?? 0}/{d.trial_like_limit}</> : null}
          {d.vip_until && <> · VIP 끝 {dateTime(d.vip_until)}</>}
        </p>
      </div>

      {d.deleted_at && d.data_purge_at && (
        <div className="mb-6">
          <WithdrawnNotice purgeAt={d.data_purge_at} purged={!d.profile && !(d.photos?.length ?? 0)} />
        </div>
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,24rem)_1fr]">
        <div className="space-y-4">
          {d.profile ? <ProfileCard card={d.profile} /> : <Notice>
              공개 프로필이 없습니다 (탈퇴 등).
              {(d.deleted_nickname || d.gender) && (
                <span className="mt-1 block">
                  탈퇴 전 닉네임 {d.deleted_nickname ?? "—"} · 성별 {d.gender ? GENDER_LABEL[d.gender] : "—"}
                </span>
              )}
            </Notice>}
          {d.campus && (
            <p className="text-[13px] text-ink-soft">
              실제 소속: {d.campus.name} · {d.department?.name ?? "학과 미선택"}
              <span className="block text-[12px] text-ink-faint">카드에는 본인 공개 설정에 따라 숨겨질 수 있어요.</span>
            </p>
          )}
          {d.profile && (
            <p className="text-[13px] text-ink-soft">
              성별 {d.gender ? GENDER_LABEL[d.gender] : "—"} · 원하는 상대 {d.preferred_gender ? GENDER_LABEL[d.preferred_gender] : "—"} · 외모 등급{" "}
              {d.appearance_tier ? TIER_LABEL[d.appearance_tier] : <span className="text-brick">없음 (추천에 안 나옴)</span>}
              <span className="block text-[12px] text-ink-faint">외모 등급은 내부 전용이에요. 사용자에게 보이지 않아요.</span>
            </p>
          )}
        </div>
        <div className="space-y-10">
          {admin.can("users:status") && (
            <StatusForm key={d.user_id} userId={d.user_id} current={d.status} deleted={!!d.deleted_at} onDone={() => load(!!d.private)} />
          )}

          {admin.can("users:status") && (!d.deleted_at || d.match_suspended) && (
            <MatchSuspensionForm
              key={`${d.user_id}-${d.match_suspended}`}
              userId={d.user_id}
              suspended={!!d.match_suspended}
              since={d.match_suspended_at ?? null}
              hiddenCount={d.hidden_matches ?? 0}
              onDone={() => load(!!d.private)}
            />
          )}

          {admin.can("users:department") && d.campus && !d.deleted_at && (
            <DepartmentForm key={`${d.user_id}-${d.department?.id}`} userId={d.user_id} campusId={d.campus.id} current={d.department} onDone={() => load(!!d.private)} />
          )}

          {admin.can("users:gender") && d.profile && !d.deleted_at && (
            <GenderForm
              key={`${d.user_id}-${d.gender}-${d.preferred_gender}`}
              userId={d.user_id}
              gender={d.gender ?? "FEMALE"}
              want={d.preferred_gender ?? "ANY"}
              onDone={() => load(!!d.private)}
            />
          )}

          {admin.can("payments:confirm") && !d.deleted_at && (
            <MembershipForm key={`${d.user_id}-${d.member_until}`} userId={d.user_id} onDone={() => load(!!d.private)} />
          )}

          {admin.can("payments:confirm") && !d.deleted_at && !d.membership_free && (
            <MembershipForm kind="vip" key={`vip-${d.user_id}-${d.vip_until}`} userId={d.user_id} onDone={() => load(!!d.private)} />
          )}

          {admin.can("photos:evaluate") && d.profile && !d.deleted_at && (
            <TierForm key={`${d.user_id}-${d.appearance_tier}`} userId={d.user_id} current={d.appearance_tier} onDone={() => load(!!d.private)} />
          )}

          {admin.can("photos:read") && (d.photos?.length ?? 0) > 0 && <UserPhotos key={`${d.user_id}-photos`} photos={d.photos!} />}

          {admin.can("chats:read") && <UserChats userId={d.user_id} />}

          {d.linked_accounts.length > 0 && (
            <section>
              <p className="eyebrow mb-3">같은 학교 메일로 가입했던 계정</p>
              <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                {d.linked_accounts.map((a) => (
                  <li key={a.user_id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
                    <Link href={`/admin/users/${a.user_id}`} className="font-mono font-semibold underline underline-offset-4">
                      {a.subject_code}
                    </Link>
                    <span className="text-[13px] text-ink-faint">
                      {dateTime(a.created_at)} 가입{a.deleted_at && <> · {dateTime(a.deleted_at)} 탈퇴</>} · {USER_STATUS_LABEL[a.status] ?? a.status}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[12.5px] text-ink-faint">탈퇴 후 재가입한 경우예요. 제재가 필요하면 각 계정마다 따로 처리하세요.</p>
            </section>
          )}

          {admin.can("users:private:read") && (
            <section>
              <p className="eyebrow mb-3">개인정보</p>
              {d.private ? (
                <dl className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
                  {[
                    ["이메일", d.private.email],
                    ["실명", d.private.real_name],
                    ["학번", d.private.student_id],
                    ["전화번호", d.private.phone_number],
                    ["생년월일", d.private.birth_date],
                  ].map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[6rem_1fr] px-5 py-3">
                      <dt className="text-ink-faint">{k}</dt>
                      <dd>{v ?? "—"}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <div className="space-y-3">
                  <Notice>열람하면 감사 로그에 기록됩니다. 신고 처리 등 꼭 필요한 경우에만 여세요.</Notice>
                  <Button variant="secondary" onClick={() => load(true)}>
                    개인정보 열람
                  </Button>
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </>
  );
}

type MatchRow = {
  match_id: string;
  partner: { user_id: string; subject_code: string; nickname: string | null };
  status: string;
  matched_at: string;
  ended_at: string | null;
  message_count: number;
  last_message_at: string | null;
};

const MATCH_STATUS_LABEL: Record<string, string> = { ACTIVE: "대화 중", UNMATCHED: "매칭 해제", BLOCKED: "차단으로 종료", HIDDEN: "숨김 (매칭 정지)" };

/** 이 사용자의 모든 대화방 (목록만. 내용은 눌러서 열면 감사 로그에 기록됨) */
const PHOTO_STATUS_LABEL: Record<string, string> = {
  PENDING: "검수 대기",
  IN_REVIEW: "확인 중",
  APPROVED: "승인",
  REJECTED: "반려",
  SUPERSEDED: "예전 사진",
};

// 탈퇴 후 7일 동안은 프로필·사진을 볼 수 있고, 그 뒤 자동 삭제된다 (2026-10-01)
function WithdrawnNotice({ purgeAt, purged }: { purgeAt: string; purged: boolean }) {
  if (purged) {
    return <Notice>탈퇴한 사용자예요. 보관 기간(7일)이 지나 프로필·사진은 삭제됐어요 ({dateTime(purgeAt)}).</Notice>;
  }
  return (
    <Notice>
      탈퇴한 사용자예요. 프로필·사진은 <b className="font-semibold">{dateTime(purgeAt)}</b>에 자동 삭제돼요. 그 전까지만 볼 수 있어요.
    </Notice>
  );
}

// 사진은 '보기'를 눌러야 불러온다. 볼 때마다 감사 로그(PHOTO_VIEW)가 남는다.
function UserPhotos({ photos }: { photos: NonNullable<Detail["photos"]> }) {
  const [show, setShow] = useState(false);
  return (
    <section>
      <p className="eyebrow mb-3">사진</p>
      {!show ? (
        <Button variant="secondary" size="sm" onClick={() => setShow(true)}>
          사진 보기 ({photos.length}장) · 감사 로그가 남아요
        </Button>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {photos.map((p) => (
            <figure key={p.photo_id} className="overflow-hidden rounded-card border border-line bg-paper-card">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={p.image_url} alt="사용자 사진" draggable={false} className="w-full select-none" />
              <figcaption className="px-3 py-2 text-[12px] text-ink-faint">
                {PHOTO_STATUS_LABEL[p.review_status] ?? p.review_status}
                {p.uploaded_at && <> · {dateTime(p.uploaded_at)}</>}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </section>
  );
}

function UserChats({ userId }: { userId: string }) {
  const [rows, setRows] = useState<MatchRow[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminApi<{ matches: MatchRow[] }>(`/users/${userId}/matches`)
      .then((r) => setRows(r.matches))
      .catch((e) => setError(errorMessage(e)));
  }, [userId]);

  return (
    <section>
      <p className="eyebrow mb-3">대화</p>
      {error ? (
        <Notice tone="error">{error}</Notice>
      ) : !rows ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="text-[13.5px] text-ink-faint">매칭된 상대가 없어요.</p>
      ) : (
        <ul className="divide-y divide-line rounded-card border border-line bg-paper-card text-[14px]">
          {rows.map((m) => (
            <li key={m.match_id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3">
              <span>
                <span className="font-mono">{m.partner.subject_code}</span>
                <span className="text-ink-soft"> · {m.partner.nickname ?? "(탈퇴)"}</span>
                <span className="ml-2 text-[12.5px] text-ink-faint">
                  {MATCH_STATUS_LABEL[m.status] ?? m.status} · 메시지 <span className="num">{m.message_count}</span>개
                  {m.last_message_at && <> · 마지막 {dateTime(m.last_message_at)}</>}
                </span>
              </span>
              <Link href={`/admin/chats/${m.match_id}`} className="text-[13px] underline underline-offset-4">
                대화 보기
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

type Status = "ACTIVE" | "SUSPENDED" | "BANNED" | "DELETED";

function StatusForm({ userId, current, deleted, onDone }: { userId: string; current: string; deleted: boolean; onDone: () => void }) {
  const [status, setStatus] = useState<Status>(current as Status);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/status`, { method: "PATCH", body: { status, reason } });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">계정 상태</p>
      <Segmented
        value={status}
        onChange={setStatus}
        options={
          deleted
            ? [
                { value: "DELETED", label: "탈퇴 (재가입 가능)" },
                { value: "BANNED", label: "영구 정지 (재가입 차단)" },
              ]
            : [
                { value: "ACTIVE", label: "정상" },
                { value: "SUSPENDED", label: "일시 정지" },
                { value: "BANNED", label: "영구 정지" },
              ]
        }
      />
      <Field label="사유 (감사 로그에 남아요)" htmlFor="status-reason">
        <Input id="status-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="신고 누적 (성희롱 2건)" />
      </Field>
      {deleted ? (
        <p className="text-[12.5px] text-ink-faint">탈퇴한 계정이에요. 영구 정지하면 같은 학교 메일로 다시 가입할 수 없어요.</p>
      ) : (
        status !== "ACTIVE" && <p className="text-[12.5px] text-ink-faint">정지하면 해당 사용자는 즉시 로그아웃돼요.</p>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요.</Notice>}
      <Button type="submit" variant={status === "ACTIVE" || status === "DELETED" ? "primary" : "danger"} loading={loading} disabled={status === current || reason.trim().length < 2}>
        상태 변경
      </Button>
    </form>
  );
}

/** 매칭 정지 (2026-10-05): 켜면 서로 LIKE해도 매칭이 숨겨진다. 사용자에게는 절대 알리지 않는다 */
function MatchSuspensionForm({
  userId,
  suspended,
  since,
  hiddenCount,
  onDone,
}: {
  userId: string;
  suspended: boolean;
  since: string | null;
  hiddenCount: number;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/match-suspension`, { method: "PATCH", body: { suspended: !suspended, reason } });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">매칭 정지</p>
      <p className="text-[14px]">
        {suspended ? (
          <span className="font-semibold text-brick">매칭 정지 중{since && <> · {dateTime(since)}부터</>}</span>
        ) : (
          <span className="text-ink-soft">정지 안 됨</span>
        )}
        {hiddenCount > 0 && (
          <span className="ml-2 text-[13px] text-ink-soft">
            숨겨진 매칭 <span className="num">{hiddenCount}</span>개 ·{" "}
            <Link href="/admin/match-suspensions" className="underline underline-offset-4">
              보러 가기
            </Link>
          </span>
        )}
      </p>
      <Notice>
        매칭 정지된 사람은 서로 LIKE해도 매칭이 뜨지 않아요 (상대에게도 안 보여요). 본인에게는 알림이 가지 않아요. 이미 있던 매칭과
        대화는 그대로예요. 정지를 풀어도 숨겨진 매칭은 그대로 숨김이라, &lsquo;매칭 정지된 사용자&rsquo; 화면에서 하나씩 다시 보이게 해야 해요.
      </Notice>
      <Field label="사유 (감사 로그에 남아요)" htmlFor="match-suspend-reason">
        <Input
          id="match-suspend-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={300}
          placeholder={suspended ? "확인 완료" : "프로필 확인 필요"}
        />
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요.</Notice>}
      <Button type="submit" variant={suspended ? "primary" : "danger"} loading={loading} disabled={reason.trim().length < 2}>
        {suspended ? "매칭 정지 풀기" : "매칭 정지하기"}
      </Button>
    </form>
  );
}

/** 학과 변경: 사용자는 직접 못 바꾸고, 가입한 학교 메일로 요청하면 여기서 바꾼다 */
function DepartmentForm({
  userId,
  campusId,
  current,
  onDone,
}: {
  userId: string;
  campusId: string;
  current: { id: string; name: string } | null;
  onDone: () => void;
}) {
  const [departments, setDepartments] = useState<{ id: string; name: string }[]>([]);
  const [deptId, setDeptId] = useState(current?.id ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<{ departments: { id: string; name: string }[] }>(`/campuses/${campusId}/departments`)
      .then((r) => setDepartments(r.departments))
      .catch((e) => setError(errorMessage(e)));
  }, [campusId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/department`, { method: "PATCH", body: { department_id: deptId, reason } });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">학과 변경</p>
      <Notice>요청 메일이 이 사용자가 가입한 학교 메일에서 왔는지 먼저 확인하세요 (개인정보 열람에서 이메일 확인).</Notice>
      <Field label="바꿀 학과" htmlFor="dept-change">
        <Select id="dept-change" value={deptId} onChange={(e) => setDeptId(e.target.value)}>
          <option value="" disabled>
            학과 선택
          </option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="사유 (감사 로그에 남아요)" htmlFor="dept-reason">
        <Input id="dept-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="가입 메일로 요청 (잘못 선택)" />
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요. 사용자에게 알림이 갔어요.</Notice>}
      <Button type="submit" loading={loading} disabled={!deptId || deptId === current?.id || reason.trim().length < 2}>
        학과 변경
      </Button>
    </form>
  );
}

/** 성별·원하는 성별 변경: 사용자는 가입 후 직접 못 바꾸고, 가입한 학교 메일로 요청하면 여기서 바꾼다 */
function GenderForm({ userId, gender, want, onDone }: { userId: string; gender: Gender; want: WantGender; onDone: () => void }) {
  const [g, setG] = useState<Gender>(gender);
  const [w, setW] = useState<WantGender>(want);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/gender`, {
        method: "PATCH",
        body: { gender: g !== gender ? g : null, preferred_gender: w !== want ? w : null, reason },
      });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">성별 · 원하는 상대 변경</p>
      <Notice>요청 메일이 이 사용자가 가입한 학교 메일에서 왔는지 먼저 확인하세요. 이미 생긴 좋아요·매칭은 그대로 남아요.</Notice>
      <Field label="성별">
        <Segmented<Gender>
          value={g}
          onChange={setG}
          options={[
            { value: "FEMALE", label: "여성" },
            { value: "MALE", label: "남성" },
          ]}
        />
      </Field>
      <Field label="원하는 상대">
        <Segmented<WantGender>
          value={w}
          onChange={setW}
          options={[
            { value: "MALE", label: "남성" },
            { value: "FEMALE", label: "여성" },
            { value: "ANY", label: "상관없음" },
          ]}
        />
      </Field>
      <Field label="사유 (감사 로그에 남아요)" htmlFor="gender-reason">
        <Input id="gender-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="가입 메일로 요청 (잘못 선택)" />
      </Field>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요. 사용자에게 알림이 갔어요.</Notice>}
      <Button type="submit" loading={loading} disabled={(g === gender && w === want) || reason.trim().length < 2}>
        변경
      </Button>
    </form>
  );
}

function membershipLabel(d: Detail): string {
  if (d.membership_free) return "이용권 무료 (테스트 계정)";
  switch (d.membership_status) {
    case "active":
      return `이용권 끝 ${d.member_until ? dateTime(d.member_until) : "—"}`;
    case "banked":
      return `이용권 ${d.member_days_banked ?? 0}일 대기 (사진 검수 후 시작)`;
    case "expired":
      return `이용권 끝남 (${d.member_until ? dateTime(d.member_until) : "—"})`;
    default:
      return "이용권 없음";
  }
}

/** 이용권(또는 VIP) 기간 늘리기/줄이기 (2026-10-04 D8, VIP는 2026-10-06). 입금 확인 지연·서버 장애 보상, 실수 정정용. 최고 관리자만 */
function MembershipForm({ userId, onDone, kind = "member" }: { userId: string; onDone: () => void; kind?: "member" | "vip" }) {
  const isVip = kind === "vip";
  const label = isVip ? "VIP" : "이용권";
  const labelObj = isVip ? "VIP를" : "이용권을";
  const [days, setDays] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);
  const n = Number(days);
  const valid = Number.isInteger(n) && n !== 0 && Math.abs(n) <= 60 && reason.trim().length >= 2;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!window.confirm(`${labelObj} ${n > 0 ? `${n}일 늘릴까요` : `${-n}일 줄일까요`}?`)) return;
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/${isVip ? "vip-adjust" : "membership-adjust"}`, { method: "POST", body: { days: n, reason } });
      setOk(true);
      setDays("");
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">{label} 기간 조정</p>
      <Field label="일수 (늘리기는 양수, 줄이기는 음수, 최대 60)" htmlFor={`${kind}-days`}>
        <Input id={`${kind}-days`} inputMode="numeric" value={days} onChange={(e) => setDays(e.target.value.trim())} placeholder="예: 3 또는 -2" />
      </Field>
      <Field label="사유 (감사 로그에 남아요)" htmlFor={`${kind}-reason`}>
        <Input id={`${kind}-reason`} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="입금 확인 지연 보상" />
      </Field>
      <p className="text-[12.5px] text-ink-faint">
        남아 있으면 끝나는 날에서 더하거나 빼요. 끝난 사람은 오늘부터 더해요. 사용자에게 알림은 가지 않아요.
        {isVip && " VIP에는 기본 이용권이 포함돼서, VIP 기간 동안은 기본 이용권이 없어도 좋아요를 쓸 수 있어요."}
      </p>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요.</Notice>}
      <Button type="submit" loading={loading} disabled={!valid}>
        기간 조정
      </Button>
    </form>
  );
}

/** 외모 등급만 다시 정하기 (점수는 그대로). 등급 기능 이전에 평가된 사용자도 여기서 채운다 */
function TierForm({ userId, current, onDone }: { userId: string; current: AppearanceTier | null; onDone: () => void }) {
  const [tier, setTier] = useState<AppearanceTier | "">(current ?? "");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    setOk(false);
    try {
      await adminApi(`/users/${userId}/appearance-tier`, { method: "PATCH", body: { tier, reason } });
      setOk(true);
      setReason("");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="eyebrow">외모 등급 (내부 전용)</p>
      <Segmented<AppearanceTier | ""> value={tier} onChange={setTier} options={TIER_OPTIONS} />
      <Field label="사유 (감사 로그에 남아요)" htmlFor="tier-reason">
        <Input id="tier-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="등급 기준 재검토" />
      </Field>
      <p className="text-[12.5px] text-ink-faint">사용자에게 알림이 가지 않아요. 평가 점수는 그대로 두고 등급만 바꿔요.</p>
      {error && <Notice tone="error">{error}</Notice>}
      {ok && <Notice tone="ok">변경했어요.</Notice>}
      <Button type="submit" loading={loading} disabled={!tier || tier === current || reason.trim().length < 2}>
        등급 저장
      </Button>
    </form>
  );
}
