# MiniOps — Final Local Test Build

A polished, small-scale PagerDuty-style incident management platform designed to be
tested locally with Docker Compose before AWS/EKS deployment.

## Local requirements
- Docker
- Docker Compose v2

## Start
```bash
cp .env.example .env
docker compose up --build
```

Open:
- http://localhost:5173
- API docs: http://localhost:8000/docs
- Mailpit: http://localhost:8025

## Demo accounts
- Global Admin: `admin@miniops.example.com` / `admin123`
- Engineer: `engineer@miniops.example.com` / `engineer123`

## Smoke test
1. Login as admin.
2. Create a team.
3. Create a service.
4. Create an integration/API key.
5. Send a test alert.
6. Open the generated incident.
7. Assign it to an engineer.
8. Acknowledge it.
9. Add a note.
10. Resolve it.
11. Inspect the incident timeline.
12. Open Mailpit and inspect notifications.

## Important
This build is the application/local validation stage. AWS infrastructure, EKS,
Terraform, Helm and ArgoCD are deliberately kept for the next deployment stage.
The goal is to validate the product and its container boundaries first.
