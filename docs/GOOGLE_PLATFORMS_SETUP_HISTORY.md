# Google Platforms Setup History

This document records the Google setup performed for the Marketing Agent system and explains what each Google platform is used for.

## Google Platforms Used

Google Search Console:

- proves domain ownership;
- reports Google Search impressions, clicks, CTR, average position, queries, and pages;
- helps monitor indexing and discoverability.

Google Analytics 4:

- measures visitor sessions and engagement;
- receives browser events from generated pages;
- provides page-level behavior metrics.

Google Cloud:

- hosts API enablement and credentials;
- stores service account identity;
- stores OAuth clients for Google Ads authorization.

Google Ads:

- gives paid campaign reporting and future paid campaign automation;
- requires a developer token, OAuth credentials, refresh token, and manager/customer IDs.

Google OAuth:

- lets the backend obtain authorized access to Google Ads through a refresh token.

Important:

The app is not hosted on Google Cloud. Google platforms provide analytics, search, and ads integrations.

## Search Console Setup Performed

Domain:

```text
agenticgrowthlabs.com
```

Search Console property:

```text
sc-domain:agenticgrowthlabs.com
```

Steps completed:

1. Opened Google Search Console.
2. Selected Domain property.
3. Entered `agenticgrowthlabs.com`.
4. Copied Google TXT verification token.
5. Added TXT record in AWS Route 53 DNS.
6. Verified domain ownership in Search Console.
7. Added service account as a Search Console user with Full access.
8. Confirmed Search Console property appears in the app config.

Why this matters:

- Google Search Console is the source of search impressions, clicks, CTR, position, queries, and indexing visibility.

Expected delay:

- New domain and new pages may show little or no Search Console data initially.
- Google needs to crawl, index, rank, and process reports.
- This can take hours to days, sometimes longer for new domains.

## GA4 Setup Performed

GA4 measurement ID:

```text
G-KZ3N4G2S20
```

GA4 property ID:

```text
544328945
```

Steps completed:

1. Created or selected GA4 account/property for Agentic Growth Labs.
2. Created a web data stream for `https://agenticgrowthlabs.com`.
3. Collected the web measurement ID.
4. Collected the property ID.
5. Added the measurement ID to production configuration.
6. Added service account access to GA4.
7. Enabled GA4 Data API in Google Cloud.
8. Confirmed production app reads GA4 values.

Why this matters:

- The measurement ID sends browser-side tracking events.
- The property ID lets the backend read GA4 analytics through the Data API.

Expected delay:

- GA4 Realtime may show activity quickly.
- Standard reports and Data API rows can lag.

## Google Cloud Setup Performed

Google Cloud project:

```text
innate-beacon-433717-d2
```

Service account:

```text
marketing-agent-seo-sync@innate-beacon-433717-d2.iam.gserviceaccount.com
```

APIs enabled:

- Google Search Console API;
- Google Analytics Data API;
- Google Ads API.

Credentials created:

- service account JSON for Search Console and GA4 reads;
- OAuth client ID and client secret for Google Ads authorization.

Important security note:

Service account JSON and OAuth client secret are secrets. They must stay in AWS environment/SSM storage and never be committed to git.

## Google Ads Setup Performed

Google Ads manager account:

```text
849-129-3027
```

Steps completed:

1. Created Google Ads manager account.
2. Opened Admin -> API Center.
3. Added API contact and company details.
4. Created developer token.
5. Applied for Basic Access.
6. Filled Google Ads API Token Application.
7. Submitted application to Google Ads API Compliance team.
8. Enabled Google Ads API in Google Cloud.
9. Configured OAuth consent.
10. Created OAuth client ID and client secret.
11. Generated refresh token using OAuth Playground.
12. Added Google Ads credentials to AWS environment.

Production values needed:

```text
GOOGLE_ADS_ENABLED=true
GOOGLE_ADS_DEVELOPER_TOKEN=<secret>
GOOGLE_ADS_CLIENT_ID=<secret>
GOOGLE_ADS_CLIENT_SECRET=<secret>
GOOGLE_ADS_REFRESH_TOKEN=<secret>
GOOGLE_ADS_LOGIN_CUSTOMER_ID=8491293027
GOOGLE_ADS_CUSTOMER_ID=8491293027
GOOGLE_ADS_API_VERSION=v23
```

Important:

The app can be configured before Google approves Basic Access. However, live Google Ads API calls may fail or be restricted until Google approves the token.

Production app behavior:

- `Run growth suite` reads/report readiness and does not create ads by itself.
- `Draft Google Ads plan` creates an internal draft in the Marketing Agent database.
- `Validate` sends a validate-only request to Google Ads where possible.
- `Push paused campaign` sends a mutate request to Google Ads only after explicit owner approval.
- New campaigns, ad groups, ads, and keywords are pushed as paused resources to prevent accidental spend.

## OAuth Refresh Token

Purpose:

- the refresh token lets the backend get short-lived access tokens without asking the owner to manually log in each time.

Why it matters:

- access tokens expire quickly;
- refresh tokens let production jobs keep working.

Production concern:

- refresh tokens must be generated from the production OAuth app, not temporary playground-only credentials.
- after OAuth app publishing, use the production client ID/secret and store the refresh token securely.

## AWS Configuration Names

Google-related values are expected as environment variables or SSM-backed Elastic Beanstalk options:

```text
GA4_MEASUREMENT_ID
GA4_PROPERTY_ID
GOOGLE_SEARCH_CONSOLE_SITE_URL
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_ADS_ENABLED
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_LOGIN_CUSTOMER_ID
GOOGLE_ADS_CUSTOMER_ID
GOOGLE_ADS_API_VERSION
```

Current production health check should show:

```json
{
  "openai_configured": true,
  "dataforseo_configured": true,
  "google_ads_configured": true
}
```
