import { Brand } from "@/components/Brand";

/** 로그인·가입·관리자 로그인 공통 틀 */
export function AuthFrame({ children, footer, sub }: { children: React.ReactNode; footer?: React.ReactNode; sub?: string }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="px-5 py-6 sm:px-8">
        <Brand sub={sub} href={sub ? "/admin" : "/"} />
      </header>
      <main className="flex flex-1 items-start justify-center px-5 pb-16 pt-6 sm:pt-14">
        <div className="w-full max-w-[25rem]">{children}</div>
      </main>
      {footer && <footer className="px-5 pb-8 text-center text-[13px] text-ink-faint">{footer}</footer>}
    </div>
  );
}
