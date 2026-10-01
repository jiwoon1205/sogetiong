import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "훕팅 — 우리 학교, 익명으로", template: "%s · 훕팅" },
  description: "같은 학교 학생끼리, 이름과 얼굴 대신 어떤 사람인지로 먼저 만나는 대학생 전용 익명 소개팅.",
  // 아이폰 "홈 화면에 추가"로 열면 사파리 주소창 없이 앱처럼 열리게 (아이콘은 app/apple-icon.png)
  appleWebApp: { capable: true, title: "훕팅", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#F6F3EE",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font -- App Router에서는 layout이 모든 페이지에 적용됨 */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500;600&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
