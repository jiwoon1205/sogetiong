/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // 서버 배포용: 실행에 필요한 파일만 .next/standalone 에 모은다 (Docker 이미지가 작아짐)
  output: "standalone",
  // /api/* 요청을 FastAPI로 넘긴다 → 브라우저에서는 화면과 API가 같은 주소(localhost:3000)로 보인다.
  // 덕분에 로그인 쿠키가 자연스럽게 오가고 CORS 설정이 필요 없다.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
