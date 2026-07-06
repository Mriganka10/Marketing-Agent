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
