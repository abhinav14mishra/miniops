# MiniOps — Complete Local Incident Operations

MiniOps is a browser-first, fully local incident-management application. This is the **functional product version**, not the later AWS/DevOps edition.

It is intentionally modeled around operational patterns found in GoAlert and current incident-management products: services, routing keys, incidents, alert deduplication, on-call schedules, overrides, escalation policies, assignment, acknowledgements, notes, notifications and audit history.

## Included locally

- React + Vite + Nginx UI
- FastAPI API
- PostgreSQL persistence
- Redis available for the local platform
- Background escalation/notification worker
- Mailpit for local email inspection
- JWT authentication
- Global Admin / Responder / User / Team Admin roles
- Users: create, invite, enable, disable, remove
- Teams: create/delete, add/remove members
- Services: owner team, escalation policy, maintenance mode
- Routing keys: create, list, rotate, revoke
- Alert ingestion endpoint with deduplication and maintenance suppression
- Manual incident creation
- Incident lifecycle: OPEN → ACKNOWLEDGED → RESOLVED → REOPENED
- Assignment to user/team
- Incident timeline and notes
- On-call schedules with daily/weekly/monthly rotation model
- Current on-call lookup and overrides
- Escalation policies with ordered levels and user/team/schedule targets
- Background escalation processing
- Email notification delivery to Mailpit
- User notification preferences
- Audit log
- Health/readiness endpoints

## Run

```bash
cp .env.example .env
docker compose up --build
```

Open:

- MiniOps: http://localhost:5173
- Mailpit: http://localhost:8025
- API health: http://localhost:5173/health
- API readiness: http://localhost:5173/ready

Demo admin:

`admin@miniops.example.com` / `admin123`

Demo responder:

`engineer@miniops.example.com` / `engineer123`

## Fresh reset

For a clean local environment:

```bash
docker compose down -v
docker compose up --build
```

This deletes the local PostgreSQL volume.

## Alert example

Create a service and routing key in the UI, then send:

```bash
curl -X POST http://localhost:5173/api/v1/alerts \
  -H 'Content-Type: application/json' \
  -d '{
    "routing_key":"rk_REPLACE_ME",
    "title":"Production database latency",
    "message":"p95 latency exceeded 1s",
    "severity":"critical",
    "source":"prometheus",
    "dedupe_key":"db-latency-prod"
  }'
```

Sending the same dedupe key while the incident is open groups the alert into the existing incident instead of creating another incident.

## Product boundary

This local edition prioritizes **complete product behavior and browser workflows**. The second MiniOps edition will take this application and add the DevOps/platform layer: Terraform, AWS, EKS, Helm, Argo CD, GitHub Actions, observability, secrets, autoscaling, network/security controls, managed databases/cache and production deployment topology.

This is not a legal certification of commercial readiness; a real public release still needs independent security, dependency, privacy, licensing and legal review.
