# Roadmap

## Phase 1: Current Prototype

Completed:

- Business profile storage.
- Campaign creation.
- Demand signal generation.
- Landing page generation.
- Public landing pages.
- Lead capture and scoring.
- Dashboard metrics.
- Audit events.
- Refresh recommendations.
- Docker and AWS deployment notes.

## Phase 2: Production Hardening

Recommended next:

- Add user authentication.
- Add admin session management.
- Add rate limiting for public lead capture.
- Add Postgres support and migrations.
- Add CloudWatch structured logging.
- Add proper background job queue for long-running agent loops.
- Add richer audit export.

## Phase 3: Growth Integrations

Recommended:

- Google Search Console integration.
- SEMrush, Ahrefs, SerpAPI, or DataForSEO integration.
- HubSpot or Salesforce CRM sync.
- Email notification for new leads.
- Slack notifications.
- S3 asset storage.

SEO productionization details:

```text
docs/SEO_ANALYTICS_REFRESH_AGENT_GUIDE.md
```

## Phase 4: Page Optimization

Recommended:

- A/B test variants.
- Page version history.
- Conversion lift tracking.
- Content refresh scheduling.
- Auto-generated meta titles and schema markup.
- UTM campaign tracking.

## Phase 5: Multi-Tenant SaaS

Recommended:

- Organizations and workspaces.
- Per-user roles.
- Per-business billing boundaries.
- Tenant-scoped database access.
- Usage metering.
- Admin analytics.
