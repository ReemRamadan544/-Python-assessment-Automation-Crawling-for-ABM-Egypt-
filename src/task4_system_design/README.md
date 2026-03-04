# Task 4 - System Architecture Diagram

## Overview
The diagram describes a scalable automation and crawling platform. It uses RabbitMQ to distribute work, a pool of stateless workers that can scale horizontally, a SQL database for persistence, and an observability setup to track health, load, and errors. It also includes basic failover and recovery paths.

## Components

### 1) Task ingestion
Requests come from clients or API consumers through an API gateway (or ingestion API). Authentication and rate limiting sit at the entry point to control access and reduce abuse.

### 2) Message queue (RabbitMQ)
RabbitMQ is used for task distribution:
- Main queue: receives incoming jobs.
- Retry/delayed queue: used for transient failures with a backoff strategy.
- Dead letter queue (DLQ): used for jobs that exceed max retries, so they can be inspected and replayed.

For availability, RabbitMQ is assumed to run in a clustered/HA setup. If a node fails, publishers and consumers reconnect and continue.

### 3) Worker pool (horizontal scaling)
Workers are stateless services, which makes scaling straightforward. Different worker services can exist (automation, crawling, DOM scraping), and more replicas can be added when load increases. Autoscaling can be based on queue depth/lag (for example via Kubernetes HPA/KEDA or a similar mechanism).

### 4) Data layer (SQL)
A SQL database (PostgreSQL or MySQL) stores job metadata, statuses, and results. Read replicas can be used for read-heavy access patterns. Backups (and optionally point-in-time recovery) support disaster recovery.

### 5) Artifacts storage (optional)
Large artifacts such as screenshots, exported JSON, and videos can be stored in object storage (for example S3/MinIO). The database stores references/paths rather than large blobs.

### 6) Monitoring and observability
The API, workers, RabbitMQ, and the database expose signals for monitoring:
- System health: liveness/readiness checks and worker heartbeats.
- Current load: CPU/RAM, request rate, queue depth, and processing latency.
- Error logging: centralized logs, and optionally tracing for debugging.
- Alerting: notifications based on error rate or latency thresholds.

## Failover and recovery
Transient failures are handled via retries with backoff. Jobs that repeatedly fail are moved to the DLQ for inspection and replay. RabbitMQ HA reduces downtime on broker failure, and database replication plus backups allow restoration if the primary database fails.
