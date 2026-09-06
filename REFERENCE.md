# Reference and design notes

MiniOps was designed as an independent implementation, using GoAlert as a primary architectural/product reference and current public incident-management documentation as behavioral references.

Reference areas:

- Service-centric incident creation and routing
- Incident acknowledgement/resolution
- On-call schedules and rotations
- Schedule overrides
- Escalation policies with ordered levels and timeouts
- Users/teams as escalation targets
- Alert deduplication/grouping
- Maintenance/suppression concepts
- Incident notes/timeline/auditability
- Notification rules

The implementation is not a copy of GoAlert source code. MiniOps has its own API, data model, UI and local Docker composition.
