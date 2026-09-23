from fastapi import FastAPI

from app.api.v1 import admin_router, auth_router, matching_router, profiles_router
from app.db.base import Base
from app.db.session import engine

app = FastAPI(
    title="Sogetiong API",
    description="Anonymous university dating platform backend",
    version="0.1.0",
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(profiles_router, prefix="/api/v1", tags=["profiles"])
app.include_router(matching_router, prefix="/api/v1", tags=["matching"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
