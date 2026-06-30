# Owner Handoff Guide

## What You Have

Marketing Agent is a working FastAPI application with a professional dashboard and a five-agent marketing workflow.

Core loop:

Understand business -> find demand -> create pages -> capture leads -> improve pages.

## Where the Code Lives

Local path:

```text
/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Marketing-Agent
```

GitHub:

```text
Mriganka10/Marketing-Agent
```

Branch:

```text
feature/prototype_development_v1
```

## How to Run Locally

```bash
cd "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Marketing-Agent"
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8015
```

Open:

```text
http://127.0.0.1:8015
```

## Local Config

Use:

```text
.env
```

Do not commit `.env`.

Important values:

```bash
DATABASE_URL=sqlite:///./data/marketing_agent.db
OPENAI_ENABLED=true
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4.1-mini
```

## How to Demo

1. Open dashboard.
2. Save the sample business profile or enter a real business.
3. Select the business in Run Campaign.
4. Click `Launch agent loop`.
5. Scroll to Generated Pages.
6. Open a public page.
7. Submit a test lead.
8. Return to dashboard and confirm leads, visits, conversions, recommendations, and audit events.

## Validation Commands

```bash
source .venv/bin/activate
python -m pytest
python -m ruff check app tests
```

## Deployment Summary

First deployment:

- Elastic Beanstalk Docker.
- Single EC2.
- SQLite on persistent EBS or RDS Postgres.
- OpenAI key in EB environment variables.

Recommended production deployment:

- Elastic Beanstalk Docker.
- RDS Postgres.
- S3 for future assets.
- CloudWatch logs.
- HTTPS.
- `API_KEY` for admin write routes.

## Files to Know

- `app/main.py`: App startup.
- `app/api/routes.py`: API and public pages.
- `app/agents/`: Agent logic.
- `app/core/config.py`: Settings.
- `app/core/content_formatting.py`: LLM output cleanup.
- `app/models/entities.py`: Database tables.
- `app/static/`: Dashboard UI.
- `docs/`: Owner and deployment documentation.

## Immediate Recommendations

Before giving this to external users:

- Rotate the OpenAI key if it was exposed in any screenshots or chats.
- Set `API_KEY`.
- Move production database to RDS Postgres.
- Add login before public production access.
- Add rate limiting to public lead capture.

