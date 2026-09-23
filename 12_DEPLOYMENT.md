# 12. Deployment

## 1. Deployment goals

- secure and stable production service
- separate frontend and backend deployment
- managed database and storage
- environment secret management
- minimal operational complexity for MVP

## 2. Recommended stack

### Frontend
- Next.js
- TypeScript
- Tailwind CSS
- Vercel recommended for MVP simplicity

### Backend
- FastAPI + Python
- deploy to Railway, Render, Fly.io, or AWS container service

### Database
- PostgreSQL managed service

### Cache/Realtime
- Redis managed service if required

### Object storage
- AWS S3 or Cloudflare R2
- private bucket with restricted signed URLs

## 3. Option comparison

### AWS S3
Pros:
- mature ecosystem
- broad tooling
- enterprise features

Cons:
- more setup overhead

### Cloudflare R2
Pros:
- simple cost profile
- good developer experience
- easy integration for private storage patterns

Cons:
- needs familiarity with CDN and storage configuration

### Supabase Storage
Pros:
- quick setup
- convenient for early-stage apps

Cons:
- less flexible than S3/R2 for strict admin photo access patterns

### Recommended choice for MVP
- Cloudflare R2 or AWS S3 depending on team familiarity
- Prefer private bucket with signed URL access

## 4. Deployment architecture

```text
Browser
  ↓
Vercel Frontend
  ↓
FastAPI Backend
  ├── PostgreSQL (managed)
  ├── Redis (optional)
  └── Private Object Storage
```

## 5. Security deployment controls

- store secrets in environment variables or secret manager
- do not commit .env files
- restrict admin area and admin API from public deployment
- enable HTTPS only
- enforce secure cookies if used
- enable WAF or CDN protection if available
- configure rate limiting at edge or gateway

## 6. Required environment variables

- DATABASE_URL
- JWT_SECRET
- EMAIL_API_KEY
- STORAGE_ACCESS_KEY
- STORAGE_SECRET_KEY
- REDIS_URL
- APP_ENV
- ADMIN_JWT_SECRET

## 7. Deployment phases

### Phase 1: staging
- deploy backend and frontend to staging environment
- test full signup and profile flow
- test admin photo review flow
- run security regression suite

### Phase 2: production
- production DB with migration scripts
- secure secrets management
- monitoring and logs
- alerting on failed auth, upload errors, and report spikes

## 8. Monitoring

- API error rate
- login failure rate
- photo upload failures
- suspicious admin actions
- match creation rate
- chat volume
- report activity

## 9. Operational policy

- no real personal data in dev or staging unless anonymized
- production photos should use private storage and short retention rules
- use staged rollout if app is released to campus users
- keep rollback procedures ready

## 10. Launch readiness checklist

- legal/privacy policy approved
- university email verification tested
- admin roles and permissions tested
- object storage access restricted
- database migration validated
- security tests passed
- QA sign-off completed

## 11. Deployment decision summary

For MVP, a simple but secure architecture is best:
- Vercel for frontend
- FastAPI on a managed service for backend
- managed PostgreSQL
- private object storage with short-lived signed URLs
- managed Redis if needed

This keeps the system reliable and easy to maintain while preserving privacy and scalability for later app expansion.
