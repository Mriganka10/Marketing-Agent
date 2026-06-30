# Marketing Agent Project Brief

## Purpose

Marketing Agent is an AI-assisted demand generation workspace. It helps a business move through the core growth loop:

Understand business -> find demand -> create pages -> capture leads -> improve pages.

The first production prototype focuses on five agents:

- Business Memory Agent
- Research Agent
- Content/Page Creation Agent
- Lead Capture Agent
- Analytics/Refresh Agent

## Target User

The target user is a founder, marketer, growth operator, or agency owner who wants to create targeted demand pages and capture inbound leads without manually coordinating research, copywriting, lead scoring, and page refresh decisions.

## Current Product Scope

The app currently supports:

- Creating business profiles with positioning, audience, offers, competitors, and tone.
- Creating campaigns tied to a business profile.
- Running an end-to-end agent loop for demand research, landing page generation, and refresh recommendations.
- Publishing generated public landing pages.
- Capturing leads from generated pages.
- Scoring leads based on email quality, company, and message depth.
- Viewing dashboard metrics, generated pages, leads, recommendations, and audit events.
- Running with OpenAI when configured, with deterministic local fallback behavior.

## Out of Scope for Current Version

The current prototype does not yet include:

- Real keyword volume or SERP data from third-party SEO APIs.
- CRM integrations such as HubSpot, Salesforce, or Pipedrive.
- Email sending and nurture workflows.
- Multi-user login and role-based UI permissions.
- A/B testing engine.
- S3-backed media library.
- RDS migrations through Alembic.

## Success Criteria

The prototype is successful when a user can:

1. Enter business context.
2. Launch a campaign.
3. Generate multiple targeted pages.
4. Open a public page.
5. Submit a lead.
6. See the lead, conversion metrics, audit records, and refresh recommendations.

## Repository

- GitHub: `Mriganka10/Marketing-Agent`
- Branch: `feature/prototype_development_v1`
- Runtime: FastAPI + SQLite by default
- UI: Static HTML, CSS, JavaScript served by FastAPI

