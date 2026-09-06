# MiniOps — Local Release Candidate

MiniOps is a small-scale incident management control plane with browser-first administration and operations.

## Included in this local release candidate

- Global admin authentication
- User creation, disable and removal
- Teams and team membership APIs
- Services
- Service routing-key generation, rotation and revocation
- Manual incident creation
- Alert ingestion using routing keys
- Alert deduplication
- Incident lifecycle: OPEN → ACKNOWLEDGED → RESOLVED → REOPENED
- Incident timeline and notes
- Escalation policy creation and levels API
- On-call schedules and rotation members
- On-call overrides API
- Audit log
- PostgreSQL
- Redis
- Mailpit for local email testing infrastructure
- React + Nginx frontend
- Docker Compose

## Run

    cp .env.example .env
    docker compose up --build

Open:

- MiniOps: http://localhost:5173
- API docs: http://localhost:8000/docs
- Mailpit: http://localhost:8025

Demo admin:

    admin@miniops.example.com
    admin123

Demo responder:

    engineer@miniops.example.com
    engineer123

## Important release note

This package is a **local release candidate**, not a claim of legal/commercial certification. Before exposing it publicly, replace secrets, add a production email provider, configure HTTPS, backups, migrations, monitoring, security scanning and perform an application/security review.

The application is intentionally Docker-first so the same containers can become the basis for the later AWS/EKS deployment.

## Reference and release status

This local release candidate was revised using the uploaded GoAlert repository as a product/behavior reference. It is intended for functional validation before AWS deployment. It is not a claim of security certification, legal compliance, or unrestricted commercial readiness.
