# Project Memory

## Stable decisions

- Product: Smriti Raj Dentistry patient-specific QR offer management system
- Deadline: Saturday, 5 September 2026
- Release type: controlled clinic pilot
- Hosting: Railway
- Expected volume: approximately 500 patient registrations and one-time QR coupons concentrated on Sunday each week
- Production database: Railway PostgreSQL; SQLite is not suitable for the hosted pilot
- Runtime shape: public web service plus private delivery worker, using a PostgreSQL delivery outbox initially
- Authentication: one centralized clinic login; no individual doctor accounts
- Offers currently identified:
  - Free In-House Zirconia Crown
  - Free In-House Aligner Scan
- Coupon validity: ten days using server time
- Coupon usage: one successful redemption only
- QR privacy: opaque token only; no patient information in QR
- Delivery goal: confirmation and QR through email and WhatsApp
- WhatsApp: official platform only and subject to provider conversation rules
- Existing prototype: FastAPI, SQLAlchemy, SQLite, Jinja2, QR generation, basic workflow tests

## Current implementation concerns

- Prototype has insecure fallback secrets.
- Prototype uses a shared plaintext environment password comparison.
- Secure cookies, CSRF protection, rate limits, and hardened headers are missing.
- Registration bypasses parts of the existing Pydantic schema.
- Patient data and backups need an explicit protection and retention plan.
- Delivery services currently prepare messages rather than reliably sending them.
- External messaging provider credentials remain undecided.

## Working principles

- Saturday is a hard deadline, so protect the critical workflow before adding convenience features.
- Keep a fallback path: printed/downloaded QR and email can operate if WhatsApp is unavailable.
- Do not claim provider delivery is complete until tested with real accounts.
- Do not use real patient data during development or acceptance testing.
- Update this file whenever a stable requirement, decision, blocker, or completed milestone changes.

## Decisions still required

- Email provider and verified sender
- WhatsApp Business configuration and initiation method
- Final clinic identity, logo, contact details, and consent wording
- Database choice for the pilot environment
- Backup destination and person responsible for daily verification

## Milestone log

- 1 September 2026: Existing demonstration archive inspected.
- 1 September 2026: Saturday deadline established.
- 1 September 2026: Centralized login chosen instead of individual accounts.
- 1 September 2026: Pre-development blueprint created.
- 1 September 2026: Railway selected for hosting; Sunday workload confirmed at approximately 500 registrations.
- 1 September 2026: Railway selected for hosting with an expected load of about 500 registrations per week.
