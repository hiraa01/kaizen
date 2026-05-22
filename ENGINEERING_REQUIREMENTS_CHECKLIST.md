# Engineering Project Requirements Checklist

This document maps the graduation requirements to concrete features in this project.

## 1) Setup / Installation Application (Windows)
- Added `setup_windows.bat` at the repository root.
- Purpose: prepares backend + frontend dependencies and starts Docker services.

## 2) Help Application + User Guide + F1
- Added in-app help screen: `frontend/lib/features/help/presentation/pages/help_support_page.dart`.
- Connected from profile menu: **Yardim & Destek**.
- Added desktop shortcut in profile page: **F1** opens help screen.

## 3) Play Store / Apple Store Release
- This is an external deployment task and requires:
  - Developer accounts (Google Play Console / Apple Developer Program),
  - Signed release builds,
  - Store listing assets and policies.
- Codebase is prepared for Android/iOS builds; store publishing requires your Google Play / Apple Developer account.

## 4) Domain + Hosting (Web)
- This is an infrastructure/deployment task.
- Required steps:
  - Buy domain,
  - Host backend + web frontend (or reverse proxy),
  - Configure SSL and DNS.

## 5) Admin Panel / Authorization
- Added admin management API endpoints (token protected):
  - `GET /api/admin/summary`
  - `GET /api/admin/users?limit=50`
  - `PATCH /api/admin/users/{user_id}/status?is_active=true|false`
- Authorization model:
  - Uses bearer token auth,
  - Optional strict admin filtering via `ADMIN_USER_IDS` environment variable (comma-separated user IDs).

## 6) Backup + Restore
- Added database backup script: `scripts/db_backup.bat`.
- Added database restore script: `scripts/db_restore.bat`.
- These scripts operate on the Docker PostgreSQL container.

## 7) Reporting (Printable)
- Added CSV report endpoint:
  - `GET /api/reports/student/{student_id}/exam-attempts.csv`
- Added print-friendly HTML report endpoint:
  - `GET /api/reports/student/{student_id}/summary-print`
  - Contains a `Yazdir` button and browser print support.

## Quick Validation Commands
- Start services:
  - `docker compose -f docker/docker-compose.yml up -d --build`
- Check report endpoint:
  - `http://localhost:8003/api/reports/student/1/summary-print`
- Download CSV:
  - `http://localhost:8003/api/reports/student/1/exam-attempts.csv`
