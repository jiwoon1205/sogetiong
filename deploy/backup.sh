#!/usr/bin/env bash
# 매일 백업: DB + 사진 → 압축 → 구글 드라이브(rclone crypt로 암호화) 업로드
#
# 준비 (서버에서 한 번):
#   1) rclone 설치:  curl https://rclone.org/install.sh | sudo bash
#   2) remote 두 개 (자세한 방법은 12_DEPLOYMENT.md 3장)
#        gdrive       : Google Drive (우리 OAuth 클라이언트, scope drive.file)
#        gdrive-crypt : crypt, remote = gdrive:sogetiong-backup
#      ⚠️ crypt 비밀번호를 잃어버리면 백업을 영영 풀 수 없다. 비밀번호 관리자에 따로 보관할 것.
#   3) 매일 새벽 4시 자동 실행 (서버 시간대 Asia/Seoul):  sudo crontab -e
#        0 4 * * * bash /home/wldns051205/sogetiong/deploy/backup.sh >> /var/log/sogetiong-backup.log 2>&1
#
# 수동 실행:  sudo bash deploy/backup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# 백업 결과 알림 (healthchecks.io): 성공하면 주소로, 실패하면 주소/fail 로 신호를 보낸다.
# 하루 넘게 성공 신호가 없거나 실패 신호가 오면 healthchecks.io가 메일로 알려준다.
# 알림이 안 가도 백업 자체는 계속되도록 curl 실패는 무시한다.
HC_PING_URL="${HC_PING_URL:-https://hc-ping.com/0622489b-b82e-4319-81f3-38a68b334bd7}"
ping_hc() { curl -fsS -m 10 --retry 3 -o /dev/null "$HC_PING_URL$1" || true; }
trap 'ping_hc /fail' ERR
ping_hc /start
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
#    (사진 폴더가 아직 없으면 DB만. 압축 중 오류가 나면 조용히 넘어가지 않고 멈춘다)
if [ -d data/photos ]; then
  tar -czf "$ARCHIVE" -C data "$SNAPSHOT" photos
else
  tar -czf "$ARCHIVE" -C data "$SNAPSHOT"
fi
rm -f "data/$SNAPSHOT"
echo "압축 완료: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 3) 구글 드라이브로 업로드 (crypt remote라 파일 내용·이름이 암호화되어 올라감)
rclone copy "$ARCHIVE" "$REMOTE"
echo "업로드 완료: $REMOTE"

# 4) 오래된 백업 정리
rclone delete "$REMOTE" --min-age "${KEEP_REMOTE_DAYS}d"
find data/backups -name 'sogetiong-*.tar.gz' -mtime +"$KEEP_LOCAL_DAYS" -delete

echo "[$(date -Is)] 백업 끝"
ping_hc ""
