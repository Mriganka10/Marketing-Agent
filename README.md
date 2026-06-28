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
