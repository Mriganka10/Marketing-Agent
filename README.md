# Marketing Agent

A production-ready FastAPI prototype for an AI-powered multi-agent marketing loop:

Understand business -> find demand -> create pages -> capture leads -> improve pages.

## Agents

- Business Memory Agent stores company positioning, audience, offers, and campaign goals.
- Research Agent generates demand signals and buyer-intent keywords.
- Content/Page Creation Agent creates SEO landing pages from the strongest signals.
- Lead Capture Agent scores and stores inbound leads from generated pages.
- Analytics/Refresh Agent reviews page performance and creates refresh recommendations.

OpenAI is used when `OPENAI_API_KEY` is configured. Deterministic fallbacks keep the app usable in local and CI environments.

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

If `API_KEY` is set, protected write APIs require `x-api-key`.

## Docker

```bash
docker build -t marketing-agent .
docker run --env-file .env -p 8000:8000 marketing-agent
```

## Deployment

See `docs/DEPLOYMENT_AWS.md` for Elastic Beanstalk, EC2/EBS, S3, and production hardening notes.

## Documentation

- `docs/PROJECT_BRIEF.md`
- `docs/ARCHITECTURE.md`
- `docs/AGENTS.md`
- `docs/API.md`
- `docs/SETUP.md`
- `docs/DATA_MODEL_AND_AUDIT.md`
- `docs/LEAD_SCORING_AND_CONVERSION.md`
- `docs/SEO_ANALYTICS_REFRESH_AGENT_GUIDE.md`
- `docs/POSTGRES_QUERY_ARTIFACT.md`
- `docs/MODELS_AND_AGENTS.md`
- `docs/SECURITY_AND_COMPLIANCE.md`
- `docs/TESTING_AND_QA.md`
- `docs/OPERATIONS_RUNBOOK.md`
- `docs/DEPLOYMENT_AWS.md`
- `docs/AWS_DEPLOYMENT_WALKTHROUGH.md`
- `docs/ROADMAP.md`
- `docs/OWNER_HANDOFF_GUIDE.md`
