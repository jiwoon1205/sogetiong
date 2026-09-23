# 09. Admin System

## 1. Admin goals

Admin system is necessary for:
- user lifecycle management
- photo review and approval
- report resolution
- university and campus config management
- matching policy tuning
- security auditing

## 2. Admin roles

### SUPER_ADMIN
- all permissions
- role assignment
- global policy edits
- account suspension/banning
- emergency access

### MODERATOR
- report review
- user suspension
- warning issuance
- basic user moderation

### PHOTO_REVIEWER
- photo queue review
- appearance score input
- limited to photo review tasks
- no broad access to private profile details

## 3. Admin page structure

- Dashboard
- Users
- Photo Reviews
- Reports
- Bans
- Universities
- Campuses
- Departments
- Matching Settings
- System Logs

## 4. Admin dashboards

### Dashboard summary
- total users
- pending reviews
- active matches
- open reports
- account status breakdown

### User management
- filter by status
- user profile summary
- membership and verification details
- moderation actions

### Photo review queue
- image list awaiting evaluation
- original file access with restricted signed URL
- evaluation form
- approval, reject, or escalate actions

## 5. Photo review workflow

```text
User uploads photo
  ↓
Photo stored privately
  ↓
Review queue created
  ↓
Photo reviewer accesses restricted image
  ↓
Score evaluation: overall, style, grooming, photo_vibe
  ↓
Result saved to appearance_evaluations
  ↓
Public summary is generated for user profile
  ↓
Original file retention reduced
```

## 6. Admin review policy

- admins must evaluate using explicit criteria rather than personal preference alone
- criteria should be standardized with score anchors
- sensitive traits cannot be factored into appearance evaluation
- admin should not access unrelated private data beyond necessary task scope

## 7. Audit log requirements

When an admin performs the following, log it:
- photo view
- photo download attempt
- profile view
- user suspension
- user deletion
- report resolution
- evaluation update

Audit log format:
```text
admin_id
action
target_id
timestamp
ip
metadata
```

## 8. Sensitive actions

The following should be treated as high-risk actions:
- original photo view
- original photo download
- user private profile lookup
- report resolution that changes user status
- global matching policy change

These actions should require:
- stronger authorization
- audit records
- IP and user-agent tracking
- 2FA if possible

## 9. Admin security design

- separate admin API from public API
- admin auth should not share user token scope
- no direct reuse of normal user JWTs
- role configuration stored separately
- permissions stored as structured JSON or similar policy model

## 10. Additional safeguards

- short-lived signed URLs for photo access
- log access and download attempts
- restrict admin workspace to allowed IPs if needed
- require MFA on privileged accounts
- disable broad admin privileges by default

## 11. Admin policy versioning

Matching policy and review criteria should be versioned.

Example:
- matching_policy_v1
- matching_policy_v2
- review_criteria_v3

This allows rollback and audit of decisions.

## 12. Operational principles

- least privilege
- audit every sensitive action
- no direct public photo URLs
- no blanket admin access
- no “single boolean admin flag” for permission control

## 13. Admin test scenarios

- Photo reviewer can evaluate photo but cannot access unrelated user private data
- Normal user cannot call admin photo APIs
- Super admin can change user status
- Moderator can resolve report but cannot modify global policy
- Audit log is created on sensitive action
