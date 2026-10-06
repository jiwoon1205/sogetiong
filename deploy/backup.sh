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
ping_hc /start
REMOTE="${BACKUP_REMOTE:-gdrive-crypt:}"
KEEP_REMOTE_DAYS="${KEEP_REMOTE_DAYS:-30}"   # 드라이브에 보관할 기간
# 서버에는 최근 백업 N개만 남긴다 (2026-10-06: 7일치 + 배포 전 수동 백업이 8GB 넘게 쌓여 디스크가 가득 참)
# 사진이 늘수록 백업 1개도 커지므로 '개수'로 제한한다. 오래된 백업은 구글 드라이브에 30일 보관된다.
KEEP_LOCAL_COUNT="${KEEP_LOCAL_COUNT:-2}"

STAMP="$(TZ=Asia/Seoul date +%Y%m%d-%H%M)"
mkdir -p data/backups
SNAPSHOT="backups/db-$STAMP.sqlite"
ARCHIVE="data/backups/sogetiong-$STAMP.tar.gz"

# 실패하면: 만들다 만 파일을 지워서 디스크를 차지하지 않게 하고, healthchecks.io에 실패 신호
# (압축이 끝난 파일은 업로드에 실패해도 남겨 둔다 → 나중에 수동으로 올릴 수 있게)
ARCHIVE_DONE=0
on_error() {
  rm -f "data/$SNAPSHOT"
  [ "$ARCHIVE_DONE" = 1 ] || rm -f "$ARCHIVE"
  ping_hc /fail
}
trap on_error ERR

# 시작 전 디스크 여유 확인 (1GB 미만이면 백업하지 않고 실패 알림 → 디스크가 꽉 차는 것을 막는다)
FREE_KB="$(df -Pk data | awk 'NR==2 {print $4}')"
if [ "$FREE_KB" -lt 1048576 ]; then
  echo "[$(date -Is)] 디스크 여유가 1GB 미만이라 백업을 건너뜀 (남은 공간: $((FREE_KB / 1024))MB)"
  ping_hc /fail
  exit 1
fi

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
ARCHIVE_DONE=1
rm -f "data/$SNAPSHOT"
echo "압축 완료: $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# 3) 구글 드라이브로 업로드 (crypt remote라 파일 내용·이름이 암호화되어 올라감)
rclone copy "$ARCHIVE" "$REMOTE"
echo "업로드 완료: $REMOTE"

# 4) 오래된 백업 정리
rclone delete "$REMOTE" --min-age "${KEEP_REMOTE_DAYS}d"
ls -1t data/backups/sogetiong-*.tar.gz | tail -n +"$((KEEP_LOCAL_COUNT + 1))" | xargs -r rm -f

echo "[$(date -Is)] 백업 끝"
ping_hc ""
