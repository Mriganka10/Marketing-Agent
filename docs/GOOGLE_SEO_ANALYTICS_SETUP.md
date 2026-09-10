# Google SEO Analytics Production Setup

This app can run in two modes:

- `demo_with_first_party_events`: sitemap, robots, generated page tracking, lead capture, and synthetic SEO metrics are available.
- `live_google_integrated`: Google Search Console and GA4 metrics are pulled into the SEO Analytics Agent.

## Required Google Setup

1. In Google Cloud project `innate-beacon-433717-d2`, enable:
   - Google Search Console API
   - Google Analytics Data API
2. Create a service account for the Marketing Agent.
3. Create a JSON key for that service account.
4. Add the service account email to Google Search Console for the domain property `sc-domain:agenticgrowthlabs.com`.
5. Add the service account email to GA4 with Viewer access.
6. Confirm the GA4 property ID. The production property currently uses `544328945`.
7. Confirm the GA4 Web Measurement ID. The production web stream currently uses `G-KZ3N4G2S20`.

## AWS SSM Parameters

Store these values in AWS Systems Manager Parameter Store under `/marketing-agent/prod`:

```bash
aws ssm put-parameter --name /marketing-agent/prod/ga4-property-id --type SecureString --value "544328945" --overwrite --region ap-south-1
aws ssm put-parameter --name /marketing-agent/prod/ga4-measurement-id --type SecureString --value "G-KZ3N4G2S20" --overwrite --region ap-south-1
aws ssm put-parameter --name /marketing-agent/prod/google-search-console-site-url --type SecureString --value "sc-domain:agenticgrowthlabs.com" --overwrite --region ap-south-1
aws ssm put-parameter --name /marketing-agent/prod/google-service-account-json --type SecureString --value '<service-account-json>' --overwrite --region ap-south-1
```

After setting parameters, force new ECS web and worker deployments so startup reloads SSM values.

## Exact Setup Performed For Production

1. Registered and routed `agenticgrowthlabs.com` in Route 53.
2. Created HTTPS access through CloudFront and ACM.
3. Created a GA4 account/property for Agentic Growth Labs.
4. Created a Web data stream:

```text
GA4_MEASUREMENT_ID=G-KZ3N4G2S20
GA4_PROPERTY_ID=544328945
```

5. Created Google Cloud service account:

```text
marketing-agent-seo-sync@innate-beacon-433717-d2.iam.gserviceaccount.com
```

6. Downloaded the service account JSON key.
7. Stored the key in AWS SSM:

```text
/marketing-agent/prod/google-service-account-json
```

8. Verified the Search Console domain property using a Route 53 TXT record:

```text
google-site-verification=yaBLRHbyx-qoMc74G4eNj43JTtUzkObqdMfBq7WPiUE
```

9. Added the service account as a `Full` user in Search Console.
10. Added the service account as a `Viewer` in GA4.
11. Updated Search Console property config to:

```text
GOOGLE_SEARCH_CONSOLE_SITE_URL=sc-domain:agenticgrowthlabs.com
```

12. Redeployed the ECS services and confirmed:

```text
mode=live_google_integrated
ga4=live_synced
google_search_console=live_synced
```

## Runtime Checks

- `GET /api/seo/integrations` shows which credentials are configured.
- `POST /api/seo/sync` pulls live Search Console and GA4 data when credentials and permissions are valid.
- `GET /api/seo/overview` powers the SEO Analytics dashboard.
- `GET /sitemap.xml` exposes the generated pages to crawlers.
- `GET /robots.txt` points Google to the sitemap.

## Expected Production Behavior

With live credentials configured, the SEO Analytics Agent:

- imports Google Search Console page/query/country/device metrics,
- imports GA4 sessions, engaged sessions, events, and conversions by page,
- scores every generated page across technical SEO, content quality, search performance, and conversion performance,
- highlights pages needing refresh,
- feeds the Analytics/Refresh Agent with page-level recommendations.

If Google credentials are missing or Google permissions fail, the app records the failure in audit logs and falls back to first-party events plus demo metrics so the UI remains usable. Once live Google sync succeeds, the SEO dashboard uses live Google sources only for Google impressions, clicks, average position, and GA4 sessions.
