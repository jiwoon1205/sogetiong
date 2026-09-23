# 10. UI Specification

## 1. Product UX direction

The UX should feel like a safe, anonymous, campus-based social discovery product, not a generic Tinder clone.

## 2. Design goals

- mobile-first web experience
- clear onboarding and low friction registration
- trust-building presentation of anonymous data
- visible safety language
- short, guided flow
- privacy-centric copywriting

## 3. Design language

### Visual style
- soft neutral base with accent color
- high contrast for accessibility
- rounded cards and gentle shadows
- simple icons, no excessive clutter

### Typography
- clean sans-serif
- readable body copy
- strong headings for quick scanning

### Layout
- central content area with card-based flow on mobile
- larger desktop layout with side info and summary panels if needed

## 4. Core screens

### Landing
- service intro
- university selection CTA
- login button
- privacy and policy links

### Login and Register
- school email input
- verification code input
- password creation
- consent checkboxes

### Onboarding
- progress bar
- step labels:
  - school verification
  - profile setup
  - photo upload
  - matching preferences
  - start service

### Discover screen
- anonymous profile card
- age / campus / department / MBTI summary
- score summary blocks
- action buttons: Pass / Like

### Match screen
- list of matched users
- chat entry for each match
- notifications for new match

### Chat screen
- message bubbles
- match summary header
- block/report actions

### Profile screen
- public profile summary
- appearance evaluation summary
- interests and bio
- preferences / settings management

### Settings screen
- account status
- visibility preferences
- notification settings
- privacy policy link
- account deletion flow

## 5. Card design

Example card content:
- nickname
- age
- campus
- department
- MBTI
- overall impression
- style
- grooming
- short bio

Card should not show:
- real name
- email
- phone
- original photo
- private matching filters

## 6. Empty states

### No candidates
> 아직 새로운 프로필이 없습니다.
> 매칭 조건을 조금 넓히면 더 많은 사람을 만날 수 있습니다.

### Candidate shortage with filter issue
> 현재 조건으로는 추천 가능한 사람이 없습니다.
> 캠퍼스 범위를 전체 캠퍼스로 변경하면 더 많은 프로필을 볼 수 있습니다.

## 7. Safety and trust copy

Use copy that reinforces privacy, not attraction tactics. Examples:
- “익명으로 서로를 알아가는 서비스입니다.”
- “실명·연락처는 공개하지 않습니다.”
- “외모 평가는 관리자 기준으로 제공됩니다.”

## 8. Action affordances

- Like / Pass should be prominent and easy to understand
- report and block actions should be present but not intrusive
- match confirmation should be visible and celebratory without feeling like a generic dating app clone

## 9. Accessibility

- minimum color contrast
- visible focus states
- keyboard navigable controls
- text alternatives for images
- responsive layout for small screens

## 10. Mobile-first behavior

- large touch targets
- bottom action bar for key actions on mobile
- card stacking and swipe-friendly interaction patterns
- minimal top navigation complexity

## 11. UI success criteria

- user can complete onboarding in under 10 minutes
- user understands anonymity rules within first screen
- recommend card is readable and actionable
- user can find match and chat flow in under two taps
- edge states are understandable without confusion
