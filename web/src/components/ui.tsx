"use client";

import Link from "next/link";
import { forwardRef } from "react";
import { cn } from "@/lib/format";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "md" | "lg" | "sm";
  loading?: boolean;
};

const buttonBase =
  "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-45";
const buttonVariants = {
  primary: "bg-ink text-paper hover:bg-black",
  secondary: "border border-line-strong bg-transparent text-ink hover:border-ink",
  ghost: "text-ink-soft hover:text-ink",
  danger: "border border-brick/40 text-brick hover:bg-brick-wash",
};
const buttonSizes = { sm: "h-9 px-3.5 text-[13px]", md: "h-11 px-5 text-[15px]", lg: "h-[52px] px-6 text-[15px]" };

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      className={cn(buttonBase, buttonVariants[variant], buttonSizes[size], className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Dots /> : children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "primary",
  size = "md",
  className,
  children,
}: {
  href: string;
  variant?: keyof typeof buttonVariants;
  size?: keyof typeof buttonSizes;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link href={href} className={cn(buttonBase, buttonVariants[variant], buttonSizes[size], className)}>
      {children}
    </Link>
  );
}

function Dots() {
  return (
    <span className="inline-flex gap-1" aria-label="처리 중">
      {[0, 1, 2].map((i) => (
        <span key={i} className="h-1 w-1 animate-pulse rounded-full bg-current" style={{ animationDelay: `${i * 150}ms` }} />
      ))}
    </span>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
  htmlFor,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-[13px] font-medium text-ink-soft">
        {label}
      </label>
      {children}
      {error ? <p className="text-[13px] text-brick">{error}</p> : hint ? <p className="text-[12.5px] text-ink-faint">{hint}</p> : null}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cn("field", className)} {...rest} />;
});

/** 학교 이메일 입력: 앞부분만 입력받고 "@도메인"은 고정 글자로 보여줌. value/onChange는 전체 주소("abc@hufs.ac.kr")로 주고받음 */
export function EmailInput({
  id,
  value,
  onChange,
  domain = "hufs.ac.kr",
  required,
}: {
  id?: string;
  value: string;
  onChange: (email: string) => void;
  domain?: string;
  required?: boolean;
}) {
  const suffix = `@${domain}`;
  const local = value.endsWith(suffix) ? value.slice(0, -suffix.length) : value;
  return (
    <div className="field flex items-center gap-1 focus-within:border-ink">
      <input
        id={id}
        type="text"
        inputMode="email"
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        value={local}
        onChange={(e) => {
          // 전체 주소를 붙여넣어도 "@" 앞부분만 사용
          const v = e.target.value.split("@")[0].trim();
          onChange(v ? `${v}${suffix}` : "");
        }}
        required={required}
        className="min-w-0 flex-1 bg-transparent focus:outline-none"
      />
      <span className="shrink-0 select-none text-ink-soft">{suffix}</span>
    </div>
  );
}

export function Textarea({ className, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("field min-h-[96px] resize-none leading-relaxed", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("field appearance-none bg-[length:12px] pr-9", className)} style={{ backgroundImage: CHEVRON, backgroundRepeat: "no-repeat", backgroundPosition: "right 14px center" }} {...rest}>
      {children}
    </select>
  );
}

const CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 8'%3E%3Cpath d='M1 1.5l5 5 5-5' fill='none' stroke='%2355524B' stroke-width='1.4'/%3E%3C/svg%3E\")";

/** 여러 개 중 하나 고르기 (라디오 대신) */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  className,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
  className?: string;
}) {
  return (
    <div className={cn("grid auto-cols-fr grid-flow-col rounded-md border border-line bg-paper-card p-1", className)} role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-9 rounded-[5px] text-[14px] transition-colors",
            value === o.value ? "bg-ink text-paper" : "text-ink-soft hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** 토글 가능한 태그 */
export function Tag({ active, onClick, children, tone = "ink" }: { active?: boolean; onClick?: () => void; children: React.ReactNode; tone?: "ink" | "brick" }) {
  const activeCls = tone === "brick" ? "border-brick bg-brick-wash text-brick-deep" : "border-ink bg-ink text-paper";
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "rounded-full border px-3.5 py-1.5 text-[13.5px] transition-colors",
        active ? activeCls : "border-line bg-paper-card text-ink-soft hover:border-line-strong hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

export function Checkbox({ checked, onChange, children }: { checked: boolean; onChange: (v: boolean) => void; children: React.ReactNode }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 py-1.5 text-[14px] leading-snug text-ink">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="peer sr-only" />
      <span
        aria-hidden
        className={cn(
          "mt-[1px] flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[4px] border transition-colors peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-ink",
          checked ? "border-ink bg-ink" : "border-line-strong bg-paper-card",
        )}
      >
        {checked && (
          <svg viewBox="0 0 12 10" className="h-2.5 w-2.5">
            <path d="M1 5l3.2 3L11 1.5" fill="none" stroke="#F6F3EE" strokeWidth="1.8" />
          </svg>
        )}
      </span>
      <span>{children}</span>
    </label>
  );
}

export function Notice({ tone = "neutral", children }: { tone?: "neutral" | "error" | "ok"; children: React.ReactNode }) {
  const tones = {
    neutral: "border-line bg-paper-deep text-ink-soft",
    error: "border-brick/30 bg-brick-wash text-brick-deep",
    ok: "border-moss/30 bg-moss-wash text-moss",
  };
  return <div className={cn("rounded-md border px-4 py-3 text-[14px] leading-relaxed", tones[tone])}>{children}</div>;
}

/** 외적 평가 한 줄: 라벨 ··· 점수 + 가는 막대 */
export function ScoreRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="grid grid-cols-[5.5rem_1fr_1.75rem] items-center gap-3">
      <span className="text-[13px] text-ink-soft">{label}</span>
      <span className="relative h-[3px] rounded-full bg-line">
        <span className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${value * 10}%` }} />
      </span>
      <span className="num text-right text-[14px] font-semibold text-ink">{value}</span>
    </div>
  );
}

export function Spinner({ label = "불러오는 중" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-[14px] text-ink-faint">
      <Dots />
      <span>{label}</span>
    </div>
  );
}

export function PageTitle({ eyebrow, title, desc }: { eyebrow?: string; title: string; desc?: React.ReactNode }) {
  return (
    <header className="mb-8">
      {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
      <h1 className="font-serif text-[26px] font-semibold leading-tight tracking-tight text-ink">{title}</h1>
      {desc && <p className="mt-2 text-[14.5px] leading-relaxed text-ink-soft">{desc}</p>}
    </header>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/30 sm:items-center" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90dvh] w-full max-w-md overflow-y-auto overscroll-contain rounded-t-2xl border border-line bg-paper p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] sm:rounded-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-serif text-[19px] font-semibold">{title}</h2>
          <button onClick={onClose} className="text-ink-faint hover:text-ink" aria-label="닫기">
            <svg viewBox="0 0 14 14" className="h-3.5 w-3.5">
              <path d="M1 1l12 12M13 1L1 13" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
