// ESLint 설정 (Next.js 16부터 쓰는 새 형식). 예전 .eslintrc.json을 대신한다.
import nextVitals from "eslint-config-next/core-web-vitals";
import { defineConfig, globalIgnores } from "eslint/config";

export default defineConfig([
  ...nextVitals,
  {
    rules: {
      // 화면이 열릴 때 useEffect 안에서 데이터를 불러오는 패턴(load() → setState)을 여러 화면에서 쓴다.
      // 버그는 아니므로 경고로만 표시한다. 나중에 데이터 불러오기 방식을 정리할 때 다시 오류로 바꾼다.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts"]),
]);
