# 11. Test Plan

## 1. Testing goals

- functional correctness
- privacy safety
- security robustness
- onboarding reliability
- matching logic integrity
- admin controls enforcement

## 2. Unit tests

### Matching logic
- matching score calculation
- age filter logic
- campus filter logic
- department exclusion logic
- block filter logic
- like/match logic

### Example tests
- match score returns expected ranking for similar profiles
- age below min_age is rejected
- campus mismatch is rejected
- excluded department is rejected
- blocked user never appears in candidate list
- mutual like creates a match

## 3. Integration tests

### Auth
- user registers with valid school email
- verification code is accepted
- duplicate email registration fails
- login with invalid credential fails
- admin login works with correct role

### Profile
- public profile creation works
- private profile creation stores sensitive fields separately
- profile update prevents invalid field exposure

### Photo review
- photo upload succeeds
- upload file validation catches invalid types and sizes
- admin review creates appearance evaluation
- public summary is returned without private fields

### Match flow
- like without mutual like does not create match
- mutual like creates match
- matched users can open chat
- blocked user cannot reach direct chat route

### Report flow
- user can report another user
- report status updates correctly
- moderator resolves case

## 4. Security tests

- user tries to access another user’s private profile
- non-admin tries to access admin route
- admin route with insufficient role is rejected
- IDOR path manipulation is prevented
- XSS payload is sanitized in profile fields
- SQL injection payload is rejected
- upload exploit is rejected by validation and malware checks
- brute-force login or verification attempts are rate limited

## 5. Critical scenario test list

### Scenario A
A likes B; B does not like A
- expected: no match

### Scenario B
A and B like each other
- expected: match created

### Scenario C
A blocks B
- expected: B removed from search and recommendation

### Scenario D
A excludes Economics department
- B in Economics is not recommended

### Scenario E
A picks Seoul campus only
- B in Global campus is not recommended

### Scenario F
A hides department
- others cannot view department

### Scenario G
Regular user calls admin photo API
- expected: 403 or equivalent denial

### Scenario H
Regular user manipulates private profile ID
- expected: access denied

## 6. Test environment recommendations

- use test database with realistic seeded users
- isolate admin roles in separate test bootstrap
- test storage bucket with stubbed object storage
- simulate email sending with mock service
- verify rate limit by sending repeated requests
- record all security tests in CI pipeline

## 7. Regression rule

Changes to matching logic or admin permissions must run:
- unit tests for score logic
- security regression suite
- at least one end-to-end user flow test

## 8. Exit criteria

The product is ready for production only if:
- all critical scenarios pass
- no privacy exposure in API responses
- admin role restrictions are verified
- basic upload exploit checks pass
- all matching and chat flows work in QA environment
