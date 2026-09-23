# sogetiong

## 학교 이메일 인증 설정

회원가입은 `@hufs.ac.kr` 이메일 인증이 완료된 경우에만 허용됩니다. 실제 인증 메일을 보내려면 `backend/.env.example`을 복사해 `backend/.env`를 만들고 SMTP 제공자의 값을 입력하세요.

```powershell
Copy-Item backend/.env.example backend/.env
```

SMTP 계정에는 일반 비밀번호 대신 제공자가 발급한 앱 비밀번호를 사용하세요. 설정이 없으면 `/auth/send-verification`이 성공으로 처리되지 않고 이메일 발송 불가 오류를 반환합니다.

