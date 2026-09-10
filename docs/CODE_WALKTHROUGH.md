# Code Walkthrough

Last updated: 10 September 2026. This walkthrough describes the code currently deployed at `https://agenticgrowthlabs.com`.

## Runtime entry points

- `app/main.py` creates the FastAPI application and controls startup integrations.
- `app/api/routes.py` exposes business, campaign, content, lead, analytics, approval, and reporting APIs.
- `app/worker.py` consumes durable background actions from SQS.
- `Dockerfile` uses `SERVICE_MODE` to start either Uvicorn or `python -m app.worker` from the same image.

## Marketing workflow

1. `app/agents/business_memory.py` captures client positioning and goals.
2. `research.py` builds demand signals; `content.py` creates page content; `orchestrator.py` coordinates the loop.
3. `lead_capture.py` scores inbound leads and writes tenant-scoped records.
4. `seo_analytics.py`, `analytics_refresh.py`, and integrations under `app/integrations/` import performance metrics.
5. `auto_refresh_approval.py` creates refresh recommendations, snapshots versions, and preserves the explicit approve/reject/publish gate.
6. `growth_suite.py` and `paid_campaign.py` provide reporting, visibility, authority, and campaign-planning capabilities.

## Scheduled Google metrics sync

1. Production EventBridge Scheduler runs daily at 08:30 `Asia/Kolkata` and sends an action message to SQS.
2. `app/worker.py` accepts the `google_metrics_sync` action and calls `run_google_sync_once` in `app/core/google_sync_scheduler.py`.
3. Success deletes the SQS message. A failed sync is audited and re-raised so SQS can retry it and eventually route it to the DLQ.
4. With `GOOGLE_SYNC_SCHEDULER_BACKEND=eventbridge`, the web service does not start the legacy process scheduler. Local development may use `process`.

## Data, configuration, and security

- `app/core/database.py` and `app/models/entities.py` manage relational state in SQLite locally or the application's PostgreSQL logical database in production.
- `app/core/aws_ssm.py` loads encrypted production configuration from Parameter Store.
- `app/core/security.py` protects configured write APIs; `app/core/audit.py` records material actions.
- PostgreSQL URL normalization accepts common `postgres://` and `postgresql://` forms and selects the psycopg SQLAlchemy dialect.

## Recent functional and reliability changes

- Scheduled Google synchronization moved out of the always-on web process to EventBridge Scheduler and SQS.
- Sync failures now propagate to queue retry instead of being logged as if the message succeeded.
- The API, approval controls, generated public pages, analytics behavior, and public domain did not change.

## Configuration affecting the flow

Production uses `GOOGLE_SYNC_SCHEDULER_BACKEND=eventbridge`, `WORKER_QUEUE_URL`, `SERVICE_MODE`, and the existing database, SSM, Google, OpenAI, security, and public URL settings.

## Verification

Run `ruff check .` and `pytest`. The migration release passed 29 tests, followed by production health and end-to-end smoke checks.
