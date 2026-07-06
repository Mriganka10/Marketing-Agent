# Production Functional Flow

This document describes the current production workflow on `release_branch`.

Production URL:

```text
https://agenticgrowthlabs.com
```

## Current Agent Loop

```text
Business Memory -> Research -> Content/Page Creation -> Lead Capture -> SEO Analytics/Refresh
```

## 1. Business Memory Agent

Purpose:

- stores company name, website, industry, audience, value proposition, offers, competitors, and tone,
- gives later agents the business context needed to generate relevant demand signals and landing pages.

UI:

```text
Launch -> Business profile -> Save business
```

API:

```text
POST /api/businesses
GET /api/businesses
```

## 2. Research Agent

Purpose:

- creates buyer-intent demand signals,
- generates keyword/topic ideas for the selected business and campaign goal,
- assigns intent, region, priority score, and rationale.

UI:

```text
Launch -> Run campaign -> Launch agent loop
```

API:

```text
POST /api/runs
```

## 3. Content/Page Creation Agent

Purpose:

- turns demand signals into SEO landing pages,
- generates title, hero, sections, CTA, meta description, keywords, brand theme, and slug,
- publishes public pages when `Publish generated pages` is enabled.

UI:

```text
Pages -> Generated pages -> Open
```

Public page format:

```text
https://agenticgrowthlabs.com/p/{slug}
```

Public pages include:

- canonical URL,
- meta description and keywords,
- Open Graph tags,
- JSON-LD structured data,
- GA4 tracking script,
- first-party page event tracking,
- lead capture form.

## 4. Lead Capture Agent

Purpose:

- captures landing-page form submissions,
- scores leads,
- stores status and source,
- feeds dashboard and conversion metrics.

UI:

```text
Activity -> Leads
```

API:

```text
POST /api/leads
GET /api/leads
```

## 5. SEO Analytics/Refresh Agent

Purpose:

- syncs Google Search Console query/page metrics,
- syncs GA4 page sessions and engagement,
- scores each generated page,
- recommends whether to improve, wait, or scale a page pattern.

UI:

```text
SEO Analytics -> Sync SEO metrics
```

The `Page performance and refresh plan` section includes a company filter:

```text
All companies
GreyRadius
Kairoz Corporation
...
```

This allows each client/company to view only its own generated page stats.

Displayed per-page metrics:

```text
Page
Google impressions
Google clicks
CTR
Average position
GA4 sessions
Leads
Conversion rate
Recommendation
```

## Current Google Integration

Production is configured for:

```text
GA4_PROPERTY_ID=544328945
GA4_MEASUREMENT_ID=G-KZ3N4G2S20
GOOGLE_SEARCH_CONSOLE_SITE_URL=sc-domain:agenticgrowthlabs.com
```

Service account:

```text
marketing-agent-seo-sync@innate-beacon-433717-d2.iam.gserviceaccount.com
```

Runtime mode should show:

```text
live_google_integrated
```

Important behavior:

- If Google has no processed rows yet, the SEO dashboard shows zero Google impressions/clicks/sessions.
- It does not mix old demo metrics into live Google mode.
- Search Console and GA4 can take hours or days to show data after setup.

## Main Routes

```text
#overview   Executive workflow and totals
#launch     Business save and campaign launch
#seo        SEO Analytics and page refresh plan
#pages      Generated pages and recommendations
#activity   Leads and audit events
```

## Production Checks

```bash
curl https://agenticgrowthlabs.com/health
curl https://agenticgrowthlabs.com/api/seo/integrations
curl -X POST https://agenticgrowthlabs.com/api/seo/sync -H 'Content-Type: application/json' -d '{}'
curl https://agenticgrowthlabs.com/api/seo/overview
```
