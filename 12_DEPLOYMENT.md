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
docker login ghcr.io -u jiwoon1205   # 4-1 참고 (처음 한 번)
docker compose pull              # GitHub가 만들어 둔 이미지 받기
docker compose up -d
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
docker login ghcr.io -u jiwoon1205   # 4-1
docker compose pull && docker compose up -d
```

## 4. 업데이트 배포 (코드를 고친 뒤)

서버(e2-micro, 메모리 1GB)는 화면(Next.js) 빌드를 감당하지 못한다 (2026-09-29: 30분 넘게 멈춤).
그래서 **이미지는 GitHub가 만들고, 서버는 내려받기만 한다.**

```text
내 PC: git push
   ▼
GitHub Actions (.github/workflows/build-images.yml)
   backend·web 이미지를 만들어 ghcr.io에 올림 (3~5분)
   태그: latest + 커밋 번호 7자리
   ▼
서버: docker compose pull → up -d   (1~2분)
```

### 4-1. 서버에서 GitHub 이미지 저장소 로그인 (한 번만)
저장소가 비공개라 이미지도 비공개다. 서버가 내려받을 수 있게 **읽기 전용 토큰**으로 로그인한다.
1. GitHub → 오른쪽 위 프로필 → Settings → Developer settings → Personal access tokens → **Tokens (classic)** → Generate new token (classic)
2. Note: `sogetiong-server-pull`, Expiration: 원하는 기간(만료되면 다시 만들어 로그인), 권한: **`read:packages` 하나만** 체크
3. 서버에서:
   ```bash
   docker login ghcr.io -u jiwoon1205     # Password 자리에 토큰 붙여넣기 (화면에 안 보이는 게 정상)
   ```
   `Login Succeeded`가 나오면 끝. 토큰은 채팅·문서에 남기지 않는다.

### 4-2. 배포 순서 (새벽에)
1. 내 PC에서 `git push`
2. GitHub 저장소 → **Actions** 탭 → 맨 위 `build-images`가 초록 체크가 될 때까지 기다림 (3~5분)
3. 서버에서:
   ```bash
   cd ~/sogetiong
   sudo bash deploy/backup.sh     # 배포 전 백업
   git pull                       # docker-compose.yml·Caddyfile·backup.sh 같은 설정 파일 받기
   docker compose pull            # 새 이미지 내려받기
   docker compose up -d           # 새 이미지로 교체 (DB 구조 변경은 backend가 켜질 때 자동 적용)
   docker compose ps
   docker image prune -f          # 안 쓰는 예전 이미지 정리 (디스크 20GB 아끼기)
   ```
4. https://private-matching.com/health 확인 → `"version"`이 방금 푸시한 커밋 번호 7자리인지 본다
5. 휴대폰으로 사이트 → 설정 화면 맨 아래 **버전**도 같은 7자리인지 확인 (다르면 화면 이미지가 안 바뀐 것)

#### 새 기능이 화면에 안 보일 때 (2026-09-30: 나이 가로 바가 안 보이고 예전 숫자 입력 칸이 그대로였음)
- GitHub **Actions** 탭에서 `build-images`가 초록 체크인지 (빨간 X면 이미지가 안 만들어짐)
- 서버에서 `docker compose pull` → `docker compose up -d`를 했는지 (push만 하면 서버는 바뀌지 않는다)
- 서버에서 `docker compose images` → web·backend가 방금 받은 이미지인지 (`IMAGE_TAG`로 예전 번호에 고정해 두지 않았는지 `echo $IMAGE_TAG`, `.env` 확인)
- 휴대폰 브라우저 새로고침 (앱처럼 홈 화면에 추가했다면 완전히 닫았다가 다시 열기)

⚠️ 서버에서 `docker compose up -d --build`는 쓰지 않는다 (서버에서 직접 빌드 → 멈춤).

### 4-3. 되돌리기 (새 버전에 문제가 있을 때)
GitHub 저장소의 커밋 목록에서 **문제없던 커밋의 번호 7자리**를 확인한 뒤:
```bash
cd ~/sogetiong
IMAGE_TAG=a16518e docker compose pull
IMAGE_TAG=a16518e docker compose up -d
```
- 고친 버전을 다시 푸시해서 Actions가 끝나면, 평소처럼 `docker compose pull && docker compose up -d`로 최신(latest)에 돌아온다.
- ⚠️ 새 버전이 DB 구조를 바꿨다면(migrations 추가) 예전 이미지가 새 DB를 못 읽을 수 있다. 그럴 땐 배포 직전 백업으로 DB도 함께 되돌린다 (3-4 복원 참고).

## 5. 운영 체크리스트
- [ ] `deploy/backend.env`의 SECRET_KEY가 예시 값이 아님 (예시 값이면 서버가 켜지지 않음)
- [ ] https 접속 시 자물쇠 표시
- [ ] 관리자 계정 2단계 인증 등록
- [x] 백업 1회 수동 실행 + 드라이브에서 확인 + 복원 테스트 (2026-09-28)
- [x] crontab 등록 (매일 04:00)
- [ ] SECRET_KEY, crypt 비밀번호 2개를 비밀번호 관리자에 보관
