# Marketing Agent

A production-ready FastAPI application for an AI-powered multi-agent marketing loop:

Understand business -> find demand -> create pages -> capture leads -> measure SEO/analytics -> refresh pages -> report client outcomes.

## Agents

- Business Memory Agent stores company positioning, audience, offers, and campaign goals.
- Research Agent generates demand signals and buyer-intent keywords.
- Content/Page Creation Agent creates SEO landing pages from the strongest signals.
- Lead Capture Agent scores and stores inbound leads from generated pages.
- Auto Refresh + Approval Agent reviews page performance, generates a complete rewrite draft,
  waits for explicit owner approval, and publishes the approved version with snapshots and audit history.
- Growth Suite Agents cover AI visibility, backlink authority, paid campaign readiness, client reporting, and client workspace separation.

OpenAI is used when `OPENAI_API_KEY` is configured. Deterministic fallbacks keep the app usable in local and CI environments.

In AWS, set `SSM_ENABLED=true` and `SSM_PARAMETER_PATH=/marketing-agent/prod`. The ECS tasks read
and decrypt configuration from Parameter Store at startup; secrets are not copied into source or
plain-text task settings.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
touch .env
uvicorn app.main:app --reload
```

Open `http://localhost:8000`.

Keep local secrets and machine-specific settings in `.env`. This file is ignored by git.

## API

- `GET /health`
- `POST /api/businesses`
- `POST /api/campaigns`
- `POST /api/runs`
- `GET /api/pages`
- `GET /p/{slug}`
- `POST /api/leads`
- `GET /api/dashboard`
- `GET /api/audit`
- `GET /api/seo/integrations`
- `POST /api/seo/sync`
- `POST /api/recommendations/{id}/rewrite`
- `POST /api/recommendations/{id}/approve`
- `POST /api/recommendations/{id}/reject`
- `POST /api/recommendations/{id}/publish`

If `API_KEY` is set, protected write APIs require `x-api-key`.

## Docker

```bash
docker build -t marketing-agent .
docker run --env-file .env -p 8000:8000 marketing-agent
```

## Deployment

See `docs/DEPLOYMENT_AWS.md` for the current CloudFront, ALB, ECS, EventBridge, SQS, RDS, and S3 design.

## Documentation

- `docs/OWNER_SYSTEM_MANUAL.md`
- `docs/ARCHITECTURE_DEEP_DIVE.md`
- `docs/CODE_WALKTHROUGH.md`
- `docs/FUNCTIONALITY_WALKTHROUGH.md`
- `docs/AGENT_CATALOG_DETAILED.md`
- `docs/DATABASE_TABLES_AND_QUERIES.md`
- `docs/GOOGLE_PLATFORMS_SETUP_HISTORY.md`
- `docs/AWS_ENVIRONMENT_AND_SECRETS.md`
- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENTS.md`
- `docs/API.md`
- `docs/SETUP.md`
- `docs/DATA_MODEL_AND_AUDIT.md`
- `docs/LEAD_SCORING_AND_CONVERSION.md`
- `docs/SEO_ANALYTICS_REFRESH_AGENT_GUIDE.md`
- `docs/SEO_TRAFFIC_INDEXING_AND_METRICS.md`
- `docs/GOOGLE_SEO_ANALYTICS_SETUP.md`
- `docs/PRODUCTION_FUNCTIONAL_FLOW.md`
- `docs/END_TO_END_TEST_CASES.md`
- `docs/POSTGRES_QUERY_ARTIFACT.md`
- `docs/MODELS_AND_AGENTS.md`
- `docs/SECURITY_AND_COMPLIANCE.md`
- `docs/TESTING_AND_QA.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/DEPLOYMENT_AWS.md`
- `docs/AWS_DEPLOYMENT_WALKTHROUGH.md`
- `docs/ROADMAP.md`
- `docs/OWNER_HANDOFF_GUIDE.md`
