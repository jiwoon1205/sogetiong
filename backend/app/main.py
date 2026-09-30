import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin_router, auth_router, catalog_router, matching_router, me_router, safety_router
from app.core.config import get_settings
from app.core.dev_bootstrap import prepare_dev_database

settings = get_settings()
settings.validate_settings()
prepare_dev_database()  # 개발 환경이면 DB 테이블·기본 데이터 자동 준비

app = FastAPI(
    title="Sogetiong API",
    description="대학생 전용 익명 데이팅 서비스 백엔드",
    version="0.2.0",
    # 운영에서는 API 문서 화면을 숨긴다
    docs_url=None if settings.environment == "prod" else "/docs",
    redoc_url=None,
    openapi_url=None if settings.environment == "prod" else "/openapi.json",
)

# 권장 구성: Next.js가 /api/* 를 이 서버로 넘겨서(rewrites) 브라우저에서는 같은 주소로 보이게 한다.
# 그러면 CORS가 필요 없다. 아래 설정은 프론트엔드를 다른 주소에서 직접 호출할 때만 쓰인다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Client-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


API = "/api/v1"
app.include_router(auth_router, prefix=f"{API}/auth", tags=["auth"])
app.include_router(me_router, prefix=API, tags=["me"])
app.include_router(catalog_router, prefix=API, tags=["catalog"])
app.include_router(matching_router, prefix=API, tags=["matching"])
app.include_router(safety_router, prefix=API, tags=["safety"])
app.include_router(admin_router, prefix=f"{API}/admin", tags=["admin"])


@app.get("/health")
def health_check() -> dict[str, str]:
    # version = 이 서버가 어느 커밋으로 만들어졌는지 (GitHub Actions가 넣어줌, 내 PC에서는 "dev")
    # → 배포 후 https://private-matching.com/health 에서 새 버전이 떴는지 바로 확인할 수 있다
    return {"status": "ok", "version": os.environ.get("APP_VERSION", "dev")}
