#!/usr/bin/env bash
# 매일 백업: DB + 사진 → 압축 → 구글 드라이브(rclone crypt로 암호화) 업로드
#
# 준비 (서버에서 한 번):
#   1) rclone 설치:  curl https://rclone.org/install.sh | sudo bash
#   2) sudo rclone config 로 remote 두 개를 만든다
#        gdrive       : Google Drive
#        gdrive-crypt : crypt, remote = gdrive:sogetiong-backup  (비밀번호 2개 설정)
#      ⚠️ crypt 비밀번호를 잃어버리면 백업을 영영 풀 수 없다. 비밀번호 관리자에 따로 보관할 것.
#   3) 매일 새벽 4시(한국 시간) 자동 실행:  sudo crontab -e  → 아래 한 줄 추가
#        0 4 * * * bash /home/ubuntu/sogetiong/deploy/backup.sh >> /var/log/sogetiong-backup.log 2>&1
#      (서버 시간대가 UTC면 0 19 * * * 로)
#
# 수동 실행:  sudo bash deploy/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."
REMOTE="${BACKUP_REMOTE:-gdrive-crypt:}"
KEEP_REMOTE_DAYS="${KEEP_REMOTE_DAYS:-30}"   # 드라이브에 보관할 기간
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-7}"      # 서버에 남겨둘 기간

STAMP="$(TZ=Asia/Seoul date +%Y%m%d-%H%M)"
mkdir -p data/backups
SNAPSHOT="backups/db-$STAMP.sqlite"
ARCHIVE="data/backups/sogetiong-$STAMP.tar.gz"

echo "[$(date -Is)] 백업 시작: $STAMP"

# 1) DB 스냅샷: 서버가 켜져 있어도 안전하게 복사하는 SQLite backup 기능 사용
docker compose exec -T backend python - <<PY
import sqlite3
src = sqlite3.connect("/data/sogetiong.db")
dst = sqlite3.connect("/data/$SNAPSHOT")
src.backup(dst)
dst.close(); src.close()
PY

# 2) DB 스냅샷 + 사진 폴더를 하나로 압축
tar -czf "$ARCHIVE" -C data "$SNAPSHOT" photos 2>/dev/null || tar -czf "$ARCHIVE" -C data "$SNAPSHOT"
rm -f "data/$SNAPSHOT"
echo "압축 완료: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 3) 구글 드라이브로 업로드 (crypt remote라 파일 내용·이름이 암호화되어 올라감)
rclone copy "$ARCHIVE" "$REMOTE"
echo "업로드 완료: $REMOTE"

# 4) 오래된 백업 정리
rclone delete "$REMOTE" --min-age "${KEEP_REMOTE_DAYS}d"
find data/backups -name 'sogetiong-*.tar.gz' -mtime +"$KEEP_LOCAL_DAYS" -delete

echo "[$(date -Is)] 백업 끝"
