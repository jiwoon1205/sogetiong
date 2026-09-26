FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 시작할 때: DB 구조 최신화 → 기본 데이터(학교·학과·관심사·관리자 역할) 확인 → 서버 실행
# --workers 1: 요청 횟수 제한을 메모리에 저장하므로 프로세스는 1개만 쓴다 (베타 500명 규모에서 충분)
# --proxy-headers: 앞단 Caddy가 알려주는 실제 사용자 IP를 사용 (백엔드 포트는 외부에 열지 않는다)
CMD ["sh", "-c", "alembic upgrade head && python -m app.scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
