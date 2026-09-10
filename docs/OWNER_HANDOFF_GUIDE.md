# Owner Handoff Guide

## What You Have

Marketing Agent is a working FastAPI application with a professional dashboard, public landing pages, SEO analytics, Growth Suite agents, Google integrations, DataForSEO readiness, Google Ads readiness, and AWS production deployment.

Core loop:

Understand business -> find demand -> create pages -> capture leads -> measure SEO/analytics -> refresh pages -> report client outcomes.

Start with the full owner manual:

```text
docs/OWNER_SYSTEM_MANUAL.md
```

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
release_branch
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
OPENAI_MODEL=gpt-5.5
```

## How to Demo

1. Open `https://agenticgrowthlabs.com`.
2. Save the sample business profile or enter a real business.
3. Select the business in Run Campaign.
4. Click `Launch agent loop`.
5. Open `Pages`.
6. Open a public page.
7. Submit a test lead.
8. Open `Activity` and confirm the lead/audit events.
9. Open `SEO Analytics`.
10. Click `Sync SEO metrics`.
11. Use the `Company` dropdown to filter page stats for one organization.

## Validation Commands

```bash
source .venv/bin/activate
python -m pytest
python -m ruff check app tests
```

## Deployment Summary

First deployment:

- CloudFront, shared ALB, and isolated ECS web/worker services.
- Single EC2.
- SQLite on persistent EBS or RDS Postgres.
- OpenAI key in SSM/Secrets Manager.

Recommended production deployment:

- EventBridge Scheduler and SQS for the durable daily sync.
- RDS Postgres.
- Private S3 for application assets and exports.
- CloudWatch logs.
- HTTPS.
- `API_KEY` for admin write routes.

## Files to Know

- `docs/OWNER_SYSTEM_MANUAL.md`: Master system ownership guide.
- `docs/ARCHITECTURE_DEEP_DIVE.md`: Full architecture from browser to AWS, database, agents, and Google platforms.
- `docs/FUNCTIONALITY_WALKTHROUGH.md`: Feature-by-feature walkthrough from business save to Growth Suite reporting.
- `docs/AGENT_CATALOG_DETAILED.md`: Every agent, purpose, inputs, outputs, and external dependencies.
- `docs/DATABASE_TABLES_AND_QUERIES.md`: Database tables and owner SQL queries.
- `docs/GOOGLE_PLATFORMS_SETUP_HISTORY.md`: Search Console, GA4, Google Cloud, OAuth, and Google Ads setup history.
- `docs/AWS_ENVIRONMENT_AND_SECRETS.md`: AWS hosting, SSM/environment values, and secret management.
- `app/main.py`: App startup.
- `app/api/routes.py`: API and public pages.
- `app/agents/`: Agent logic.
- `app/core/config.py`: Settings.
- `app/core/content_formatting.py`: LLM output cleanup.
- `app/models/entities.py`: Database tables.
- `app/static/`: Dashboard UI.
- `docs/`: Owner and deployment documentation.
- `docs/LEAD_SCORING_AND_CONVERSION.md`: Dashboard lead score and conversion explanation.
- `docs/SEO_ANALYTICS_REFRESH_AGENT_GUIDE.md`: Client-facing SEO and Analytics/Refresh Agent explanation.
- `docs/SEO_TRAFFIC_INDEXING_AND_METRICS.md`: Explains what the agent can do for traffic/indexing, what Google controls, and the meaning of traffic, visits, leads, CTR, impressions, and ranking.
- `docs/GOOGLE_SEO_ANALYTICS_SETUP.md`: GA4 and Search Console setup performed for production.
- `docs/PRODUCTION_FUNCTIONAL_FLOW.md`: Current feature flow and production checks.
- `docs/END_TO_END_TEST_CASES.md`: Manual test cases from business save through Google search and metrics review.
- `docs/POSTGRES_QUERY_ARTIFACT.md`: PostgreSQL connection commands and SQL query artifact.

## Hosting And Mobile Clarification

The app is hosted on AWS, not Google servers.

The app can be opened on mobile through a browser at:

```text
https://agenticgrowthlabs.com
```

It is not currently published on Google Play Store. A Play Store app would require separate Android/PWA packaging, store listing, signing, screenshots, privacy policy submission, and Google Play review.

## Immediate Recommendations

Before giving this to external users:

- Rotate the OpenAI key if it was exposed in any screenshots or chats.
- Set `API_KEY`.
- Add login before public production access.
- Add rate limiting to public lead capture.
