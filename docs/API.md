# API Reference

Base URL for local development:

```text
http://127.0.0.1:8015
```

## Authentication

If `API_KEY` is set in `.env`, protected write APIs require:

```http
x-api-key: your-api-key
```

If `API_KEY` is blank, protected write APIs are open for local development.

## Health

```http
GET /health
```

Returns service health and whether OpenAI is configured.

## Business Profiles

```http
POST /api/businesses
GET /api/businesses
```

Example create payload:

```json
{
  "name": "Northstar Growth Labs",
  "website": "https://example.com",
  "industry": "B2B marketing automation",
  "audience": "Seed to Series B SaaS founders and revenue teams",
  "value_proposition": "We identify demand, create pages, capture leads, and refresh based on analytics.",
  "offers": ["SEO landing pages", "Lead capture automation"],
  "competitors": ["Clay", "Copy.ai"],
  "tone": "confident and consultative"
}
```

## Campaigns

```http
POST /api/campaigns
GET /api/campaigns
```

Example create payload:

```json
{
  "business_id": "business-profile-id",
  "name": "Q3 AI growth pages",
  "goal": "Generate qualified demo requests from high-intent searches.",
  "target_region": "United States"
}
```

## Run Agent Loop

```http
POST /api/runs
```

Example payload:

```json
{
  "campaign_id": "campaign-id",
  "publish_pages": true
}
```

Returns:

- Campaign.
- Demand signals.
- Generated landing pages.
- Refresh recommendations.

## Pages

```http
GET /api/pages
GET /api/pages/{page_id}
GET /p/{slug}
```

`/p/{slug}` renders a public landing page with a lead form.

## Leads

```http
POST /api/leads
GET /api/leads
```

Example payload:

```json
{
  "campaign_id": "campaign-id",
  "page_id": "page-id",
  "name": "Avery Buyer",
  "email": "avery@acme.com",
  "company": "Acme",
  "message": "We need a scalable content and lead capture engine."
}
```

## Recommendations

```http
GET /api/recommendations
POST /api/campaigns/{campaign_id}/refresh
```

## Dashboard

```http
GET /api/dashboard
```

Returns summary counts, recent leads, and recommendations.

## Audit

```http
GET /api/audit
```

Returns recent audit events.

## SEO Analytics

```http
GET /api/seo/integrations
GET /api/seo/overview
POST /api/seo/sync
```

`GET /api/seo/integrations` returns Google setup and sync mode.

Expected production mode:

```text
live_google_integrated
```

`GET /api/seo/overview` returns page performance cards with:

- owning business id and name,
- page URL,
- Google impressions,
- Google clicks,
- CTR,
- average position,
- GA4 sessions,
- leads,
- conversion rate,
- recommendation.

`POST /api/seo/sync` pulls Google Search Console and GA4 metrics into the database.

## Growth Suite

```http
GET /api/growth/overview
POST /api/growth/sync
```

`GET /api/growth/overview` returns:

- six agent cards,
- OpenAI/DataForSEO/Google Ads/SEO readiness,
- client workspaces partitioned by business,
- executive reporting snapshot,
- orchestration steps.

`POST /api/growth/sync` runs and persists the suite into `growth_agent_executions` and writes an audit event.

See:

```text
docs/GROWTH_SUITE_AGENTS.md
```

## Paid Ad Plans

```http
GET /api/ads/plans
POST /api/ads/plans/draft
PATCH /api/ads/plans/{plan_id}
POST /api/ads/plans/{plan_id}/validate
POST /api/ads/plans/{plan_id}/push
```

Purpose:

- drafts Google Ads Search campaign plans from existing business, campaign, and landing-page data;
- validates the plan with Google Ads API before launch;
- pushes owner-approved plans into Google Ads as paused resources;
- updates already-pushed campaign controls such as name, status, and daily budget.

Example draft payload:

```json
{
  "campaign_id": "campaign-id",
  "business_id": "business-id",
  "daily_budget": 500,
  "currency_code": "INR"
}
```

Push payload:

```json
{
  "approve_google_push": true,
  "mode": "publish"
}
```

Guardrails:

- write endpoints require `x-api-key` when `API_KEY` is configured;
- push is rejected unless `approve_google_push=true` and `mode=publish`;
- newly created Google Ads campaigns, ad groups, ads, and keywords are created as `PAUSED`;
- billing spend starts only if an owner later enables the campaign in Google Ads or explicitly changes the stored plan status.
