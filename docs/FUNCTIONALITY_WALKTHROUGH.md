# Full Functionality Walkthrough

This document explains every major feature from the owner and demo perspective.

## 1. Business Save

Screen:

```text
Launch
```

Inputs:

- business name;
- website;
- industry;
- tone;
- audience;
- value proposition;
- offers;
- competitors.

Backend endpoint:

```text
POST /api/businesses
```

Agent:

```text
Business Memory Agent
```

Database table:

```text
business_profiles
```

What happens:

- stores the company profile;
- normalizes business context;
- creates owner/audit history;
- makes the profile available to campaigns and future agents.

## 2. Campaign Creation

Screen:

```text
Launch
```

Inputs:

- business;
- campaign name;
- target region;
- campaign goal;
- publish generated pages toggle.

Backend endpoint:

```text
POST /api/campaigns
```

Database table:

```text
campaigns
```

What happens:

- creates a marketing campaign linked to one business;
- captures the campaign objective and target region;
- prepares the agent loop.

## 3. Launch Agent Loop

Screen:

```text
Launch -> Launch agent loop
```

Backend endpoint:

```text
POST /api/runs
```

Agents involved:

- Research Agent;
- Content/Page Creation Agent;
- Analytics/Refresh Agent.

Database tables:

- `demand_signals`;
- `landing_pages`;
- `refresh_recommendations`;
- `audit_events`.

What happens:

1. Research Agent creates demand signals and keyword/topic opportunities.
2. Content/Page Creation Agent converts demand signals into landing pages.
3. Pages are stored as draft or published depending on the publish toggle.
4. Analytics/Refresh Agent creates initial recommendations.
5. Audit entries are recorded.

## 4. Generated Landing Pages

Screen:

```text
Pages
```

Public route:

```text
/p/{slug}
```

Examples:

```text
https://agenticgrowthlabs.com/p/kairoz-corporation-scalable-marketing-automation-india
```

Database table:

```text
landing_pages
```

What each public page includes:

- SEO title;
- hero copy;
- page sections;
- CTA;
- lead form;
- brand theme;
- GA4 browser event support;
- first-party event support;
- public indexable URL;
- sitemap inclusion when published.

## 5. Lead Capture

Screen:

```text
Public page form
```

Backend endpoint:

```text
POST /api/leads
```

Agent:

```text
Lead Capture Agent
```

Database table:

```text
leads
```

What happens:

- visitor submits name, email, company, and message;
- system scores the lead;
- lead is tied to campaign and optionally page;
- page conversion count increases;
- dashboard and activity views update.

## 6. First-Party Events

Backend endpoint:

```text
POST /api/events
```

Database table:

```text
page_events
```

Events may include:

- page view;
- CTA click;
- form start;
- form submit;
- scroll depth;
- referrer details.

Purpose:

- gives internal analytics even before GA4/Search Console data is ready;
- supports refresh decisions;
- gives a fallback when Google data is delayed.

## 7. SEO Analytics

Screen:

```text
SEO Analytics
```

Backend endpoints:

- `GET /api/seo/overview`;
- `GET /api/seo/integrations`;
- `POST /api/seo/sync`.

Agent:

```text
SEO Analytics Agent
```

External platforms:

- Google Search Console;
- GA4.

Database tables:

- `seo_integration_connections`;
- `seo_search_metrics`;
- `analytics_page_metrics`;
- `seo_recommendation_runs`;
- `keyword_rank_snapshots`;
- `sitemap_submissions`.

What it shows:

- indexed/published page count;
- Google impressions;
- Google clicks;
- CTR;
- average position;
- GA4 sessions;
- leads;
- page health scores;
- top search queries;
- refresh recommendations.

## 8. Company Filter

Screen:

```text
SEO Analytics
```

Purpose:

- lets a GreyRadius viewer see GreyRadius page performance;
- lets a Kairoz viewer see Kairoz page performance;
- avoids mixing client reporting.

Current behavior:

- filters page performance and recommendations by business/company.

Future hardening:

- add login and role-based access control before giving direct access to external clients.

## 9. Refresh Recommendations

Screen:

```text
SEO Analytics
Activity
Growth Suite
```

Agents:

- Analytics/Refresh Agent;
- Auto Refresh + Approval Agent.

What they evaluate:

- low impressions;
- low clicks;
- poor CTR;
- poor average position;
- low sessions;
- low leads;
- weak conversion rate;
- page content quality;
- page technical quality.

What they output:

- diagnosis;
- recommended action;
- expected impact;
- refresh priority.

Important owner note:

The current production posture is human-approval-first. The system recommends and prepares improvements, but should not automatically rewrite and publish client-facing content without review unless you intentionally change that policy.

## 10. Growth Suite

Screen:

```text
Growth Suite
```

Backend endpoints:

- `GET /api/growth/overview`;
- `POST /api/growth/sync`.

Agents:

- AI Search Visibility Agent;
- Backlink / Authority Agent;
- Auto Refresh + Approval Agent;
- Paid Campaign Agent;
- Client Reporting Agent;
- Client Workspace / Access Control Agent.

External platforms:

- OpenAI;
- DataForSEO;
- Google Ads;
- GA4;
- Search Console.

What it shows:

- readiness of integrations;
- six-agent status;
- client workspaces;
- paid campaign readiness;
- authority opportunities;
- executive reporting snapshot;
- orchestration steps.

## 11. Audit And Governance

Screen:

```text
Activity
```

Backend endpoint:

```text
GET /api/audit
```

Database table:

```text
audit_events
```

What is tracked:

- business creation/update;
- campaign creation;
- agent loop runs;
- SEO syncs;
- Growth Suite syncs;
- lead and page activity where applicable.

## 12. Search Engine Discovery Flow

Generated pages become discoverable through:

1. public URL;
2. SEO metadata;
3. `robots.txt`;
4. `sitemap.xml`;
5. Search Console domain verification;
6. Google crawling and indexing;
7. Search Console metrics after processing delay.

Important:

The app can improve SEO readiness and request discovery signals through sitemap/indexing setup, but Google decides whether and when to index or rank pages.

