FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# 시작할 때 DB 구조를 최신으로 맞춘 뒤 서버 실행
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
