import type { Config } from "tailwindcss";

// 디자인 토큰: 오프화이트 종이 + 먹색 글씨 + 벽돌색 포인트 하나
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: { DEFAULT: "#F6F3EE", deep: "#EDE9E1", card: "#FBFAF7" },
        ink: { DEFAULT: "#1E1D1B", soft: "#55524B", faint: "#8C887E" },
        line: { DEFAULT: "#DDD8CD", strong: "#C7C1B4" },
        brick: { DEFAULT: "#8E3B2B", deep: "#6F2C20", wash: "#F2E6E0" },
        moss: { DEFAULT: "#46604C", wash: "#E6ECE5" },
      },
      fontFamily: {
        sans: ["Pretendard Variable", "Pretendard", "-apple-system", "system-ui", "sans-serif"],
        serif: ["'Noto Serif KR'", "Georgia", "serif"],
      },
      letterSpacing: { label: "0.14em" },
      borderRadius: { card: "10px" },
      maxWidth: { app: "30rem" },
      // 머리말 가입자 수가 살며시 나타나게 (2026-10-05)
      keyframes: { fadein: { from: { opacity: "0" }, to: { opacity: "1" } } },
      animation: { fadein: "fadein .6s ease-out" },
    },
  },
  plugins: [],
};

export default config;
