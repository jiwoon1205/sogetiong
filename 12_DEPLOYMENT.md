# 12. Deployment (베타)

## 1. 베타 구성 (사용자 500명 이하)

```text
사용자 브라우저
   │  https://private-matching.com
   ▼
[Caddy]  HTTPS 인증서 자동 발급·갱신
   ├── /api/*  → [backend]  FastAPI (프로세스 1개)
   └── 나머지  → [web]      Next.js
                    │
              서버의 ./data 폴더
              ├── sogetiong.db   (SQLite)
              ├── photos/        (원본 사진, 외부 공개 주소 없음)
              └── backups/       (최근 7일 백업)
                    │ 매일 새벽 4시
                    ▼
              구글 드라이브 (rclone crypt로 암호화, 30일 보관)
```

- 서버 1대 (GCP Compute Engine e2-micro, 서울 asia-northeast3-c, 디스크 20GB, 스왑 2GB, 고정 IP 35.216.67.226) + 도메인 `private-matching.com`
- 결정 이유: 500명 규모에서는 S3·Redis·PostgreSQL·서버 여러 대가 필요 없다. 대신 **매일 암호화 백업**으로 서버 고장에 대비한다.
- 사용자가 크게 늘면: PostgreSQL, R2/S3, Redis로 옮긴다 (코드는 이미 PostgreSQL을 지원).

| 파일 | 역할 |
|---|---|
| `docker-compose.yml` | backend·web·caddy 세 개를 한 번에 실행 |
| `deploy/Caddyfile` | HTTPS + 주소별 전달 |
| `deploy/backend.env.example` | 운영 설정 예시 (실제 파일 `deploy/backend.env`는 Git 제외) |
| `deploy/backup.sh` | 매일 백업 스크립트 |

## 2. 처음 배포하기

### 2-1. 서버 방화벽 열기 (GCP 콘솔)
VM 인스턴스 → 수정 → 방화벽에서 **HTTP 트래픽 허용**, **HTTPS 트래픽 허용** 체크.

### 2-2. 도메인 연결 (DNS)
도메인 관리 화면(구글에서 산 도메인은 현재 Squarespace Domains에서 관리)의 DNS 설정에서:

| 종류 | 이름(Host) | 값 |
|---|---|---|
| A | `@` | 서버 고정 IP |
| CNAME | `www` | `private-matching.com` |

확인: PC에서 `nslookup private-matching.com` → 서버 IP가 나오면 연결 완료 (몇 분~몇 시간 걸릴 수 있음).

### 2-3. 서버 접속
GCP 콘솔 VM 인스턴스 목록의 **SSH** 버튼 (브라우저 터미널).

### 2-4. 서버 준비 (한 번만)
```bash
# Docker 설치
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # 이후 창을 닫고 다시 접속

# 메모리 여유 공간(스왑) 2GB — 화면 빌드할 때 메모리 부족 방지
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 2-5. 코드 받기 + 설정
```bash
git clone https://github.com/<GitHub계정>/sogetiong.git
cd sogetiong
cp deploy/backend.env.example deploy/backend.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # 나온 값을 SECRET_KEY에
nano deploy/backend.env    # SECRET_KEY, SMTP_USERNAME/PASSWORD/FROM_EMAIL 채우기
```
- SECRET_KEY는 **비밀번호 관리자에도 따로 보관**. 운영 시작 후에는 바꾸지 않는다.
- Gmail로 메일을 보낼 때: 구글 계정 → 보안 → 2단계 인증 → **앱 비밀번호** 생성 → `SMTP_PASSWORD`. `SMTP_FROM_EMAIL`은 그 Gmail 주소.

### 2-6. 실행
```bash
docker compose up -d --build     # 처음엔 5~10분
docker compose ps                # 세 개 모두 running 이면 OK
docker compose logs -f backend   # 오류 확인 (Ctrl+C로 나가기)
```
브라우저에서 https://private-matching.com 접속 → 자물쇠 표시가 보이면 HTTPS까지 완료.

### 2-7. 관리자 계정 만들기
```bash
docker compose exec backend python -m app.scripts.create_admin --email 내이메일 --role SUPER_ADMIN
```
출력되는 2단계 인증 비밀키를 Google Authenticator 등에 바로 등록.

## 3. 백업 (구글 드라이브, 매일)

### 3-1. rclone 설치·연결 (한 번만) — 2026-09-28 완료
```bash
curl https://rclone.org/install.sh | sudo bash
```
1. **gdrive** (Google Drive): rclone 공용 client_id는 한도 초과가 잦아서 **우리 OAuth 클라이언트**(GCP 콘솔 → API 및 서비스 → 사용자 인증 정보 → 데스크톱 앱 "rclone-backup", 동의 화면 앱 이름 private-matching-backup)를 쓴다. scope는 `drive.file` (rclone이 만든 파일에만 접근).
   서버엔 브라우저가 없으므로: 서버에서 `sudo rclone config create gdrive drive client_id=... client_secret=... scope=drive.file config_is_local=true`를 백그라운드로 실행 → 나온 인증 주소를 PC 브라우저에서 열어 jiwoon@private-matching.com으로 허용 → 브라우저 주소창에 뜬 `http://127.0.0.1:53682/?...code=...` 주소를 서버에서 `curl`로 호출.
2. **gdrive-crypt** (암호화): 비밀번호 2개를 서버가 무작위로 만들어 `/root/backup-passwords.txt`(관리자만 읽기 가능)에 저장하고 그대로 설정.
   ```bash
   sudo bash -c 'umask 077; P1=$(openssl rand -hex 24); P2=$(openssl rand -hex 24); printf "rclone crypt password : %s\nrclone crypt password2: %s\n" "$P1" "$P2" > /root/backup-passwords.txt; rclone config create gdrive-crypt crypt remote=gdrive:sogetiong-backup filename_encryption=standard directory_name_encryption=true password="$P1" password2="$P2" --obscure'
   ```
3. 비밀번호 보관: `sudo cat /root/backup-passwords.txt` → 두 줄을 **비밀번호 관리자에 저장** → 저장했으면 `sudo rm /root/backup-passwords.txt`.

⚠️ crypt 비밀번호를 잃어버리면 백업을 **영영 풀 수 없다**. 서버가 통째로 고장 나면 서버 안의 설정도 함께 사라지므로, 비밀번호 관리자에 있는 값이 유일한 열쇠다.

### 3-2. 수동으로 한 번 실행해 보기
```bash
cd ~/sogetiong
sudo bash deploy/backup.sh
sudo rclone ls gdrive-crypt:      # 올라간 백업 확인 (드라이브에서는 이름이 암호화되어 보임)
```

### 3-3. 매일 자동 실행 (등록 완료)
서버 시간대가 Asia/Seoul이므로 그대로 새벽 4시.
```bash
sudo crontab -l
0 4 * * * bash /home/wldns051205/sogetiong/deploy/backup.sh >> /var/log/sogetiong-backup.log 2>&1
```
잘 돌았는지 확인: `sudo tail -20 /var/log/sogetiong-backup.log`

### 3-4. 복원 (서버가 고장났을 때)
새 서버에서 2-4, 2-5까지 진행한 뒤 (SECRET_KEY는 **예전 값 그대로**):
```bash
sudo rclone copy gdrive-crypt:sogetiong-날짜.tar.gz /tmp/
mkdir -p data && sudo tar -xzf /tmp/sogetiong-날짜.tar.gz -C data
sudo mv data/backups/db-날짜.sqlite data/sogetiong.db
docker compose up -d --build
```

## 4. 업데이트 배포 (코드를 고친 뒤)
```bash
cd ~/sogetiong
git pull
docker compose up -d --build     # DB 구조 변경(Alembic)은 backend가 켜질 때 자동 적용
```
배포 전에 `sudo bash deploy/backup.sh`로 백업 한 번 해두면 안전하다.

## 5. 운영 체크리스트
- [ ] `deploy/backend.env`의 SECRET_KEY가 예시 값이 아님 (예시 값이면 서버가 켜지지 않음)
- [ ] https 접속 시 자물쇠 표시
- [ ] 관리자 계정 2단계 인증 등록
- [x] 백업 1회 수동 실행 + 드라이브에서 확인 + 복원 테스트 (2026-09-28)
- [x] crontab 등록 (매일 04:00)
- [ ] SECRET_KEY, crypt 비밀번호 2개를 비밀번호 관리자에 보관
