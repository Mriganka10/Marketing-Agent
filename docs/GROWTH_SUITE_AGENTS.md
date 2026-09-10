# Growth Suite Agents

This release extends the original marketing loop with six production-oriented agents. The core flow remains:

Business memory -> research -> page creation -> lead capture -> SEO analytics -> refresh.

The new Growth Suite adds the client package layer around that loop:

1. AI Search Visibility Agent
   - Checks whether a brand is likely to appear in ChatGPT/OpenAI-style answer journeys.
   - Uses the configured OpenAI model when `OPENAI_API_KEY` is present.
   - Current production scope is OpenAI/ChatGPT only; Perplexity, Gemini, and other answer engines remain future scope.

2. Backlink / Authority Agent
   - Uses DataForSEO credentials to call the live Backlinks Summary API for domain authority, referring-domain, backlink, and spam-score signals.
   - Uses the Growth Suite `Authority target` dropdown to decide which company's website should be sent to DataForSEO.
   - Defaults to the first real company website and skips placeholder domains such as `example.com`, `localhost`, or `127.0.0.1` unless the owner explicitly selects that business.
   - Keeps a deterministic fallback so client demos still work if DataForSEO balance, permissions, or endpoint access is not ready.
   - Helps decide which pages need external authority support, not just on-page editing.

3. Auto Refresh + Approval Agent
   - Reviews page health, Google impressions, clicks, CTR, position, GA4 sessions, leads, and conversion rate.
   - Converts weak page signals into refresh recommendations.
   - Keeps human approval as the production guardrail before publishing major changes.

4. Paid Campaign Agent
   - Connects to Google Ads API using developer token, OAuth client, refresh token, and customer IDs.
   - Reads campaign performance once Google Ads API access is approved.
   - Drafts Search campaign plans from approved business, campaign, and landing-page data.
   - Validates drafts against Google Ads API before publishing.
   - Creates or updates Google Ads campaigns only after explicit owner approval.
   - Creates new campaigns, ad groups, ads, and keywords as paused resources to avoid accidental billing.

5. Client Reporting Agent
   - Packages SEO, campaign, lead, and refresh performance into an executive snapshot.
   - Supports client-facing reporting by business.

6. Client Workspace / Access Control Agent
   - Partitions pages, leads, reports, and SEO metrics by `business_id`.
   - Gives GreyRadius, Kairoz, or any future client a separated workspace view.
   - Current implementation is workspace partitioning and governance-ready UI. Full authenticated client login is the next hardening step before external self-serve rollout.

## API Endpoints

- `GET /api/growth/overview`
  - Reads the full suite status, agent cards, client workspaces, report snapshot, and integration readiness.

- `POST /api/growth/sync`
  - Runs the suite and writes `growth_agent_executions` plus an audit event.
  - Requires the same `x-api-key` protection as other write APIs when `API_KEY` is configured.

## AWS Environment Variables

The deployment script reads production values from AWS Systems Manager Parameter Store under:

```text
/kairoz/production/marketing
```

Add these values as SecureString parameters before a deploy if you want the live production site to use them immediately. If they are not present yet, the deployed UI will still work and will show those integrations as pending.

Required for OpenAI visibility:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-5.5`
- `OPENAI_REASONING_EFFORT=medium`
- `OPENAI_EMBEDDING_MODEL=text-embedding-3-large`

Already used by SEO/GA4/GSC:

- `PUBLIC_BASE_URL=https://agenticgrowthlabs.com`
- `GA4_MEASUREMENT_ID=G-KZ3N4G2S20`
- `GA4_PROPERTY_ID=544328945`
- `GOOGLE_SEARCH_CONSOLE_SITE_URL=sc-domain:agenticgrowthlabs.com`
- `GOOGLE_SERVICE_ACCOUNT_JSON=<entire service-account JSON as one line>`

Required for DataForSEO:

- `DATAFORSEO_ENABLED=true`
- `DATAFORSEO_LOGIN=<DataForSEO API login>`
- `DATAFORSEO_PASSWORD=<DataForSEO API password>`

Live DataForSEO behavior:

- The app first checks account readiness through DataForSEO user data.
- The Backlink / Authority Agent then calls `POST /v3/backlinks/summary/live` for the selected business domain.
- If the backlinks endpoint returns valid data, backlink metrics are labeled `Live DataForSEO`.
- If the account is configured but the endpoint returns an authorization, balance, or data error, the card remains available and the affected metrics are labeled `Demo fallback`.
- The public readiness response is sanitized and does not expose the DataForSEO API login or password.

SSM parameter names:

```text
/kairoz/production/marketing/dataforseo-enabled
/kairoz/production/marketing/dataforseo-login
/kairoz/production/marketing/dataforseo-password
```

Required for Google Ads:

- `GOOGLE_ADS_ENABLED=true`
- `GOOGLE_ADS_DEVELOPER_TOKEN=<Google Ads developer token>`
- `GOOGLE_ADS_CLIENT_ID=<Google Cloud Web OAuth client ID>`
- `GOOGLE_ADS_CLIENT_SECRET=<Google Cloud Web OAuth client secret>`
- `GOOGLE_ADS_REFRESH_TOKEN=<production refresh token>`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID=8491293027`
- `GOOGLE_ADS_CUSTOMER_ID=8491293027`
- `GOOGLE_ADS_API_VERSION=v23`

SSM parameter names:

```text
/kairoz/production/marketing/google-ads-enabled
/kairoz/production/marketing/google-ads-developer-token
/kairoz/production/marketing/google-ads-client-id
/kairoz/production/marketing/google-ads-client-secret
/kairoz/production/marketing/google-ads-refresh-token
/kairoz/production/marketing/google-ads-login-customer-id
/kairoz/production/marketing/google-ads-customer-id
/kairoz/production/marketing/google-ads-api-version
```

For Google Ads, keep `GOOGLE_ADS_CUSTOMER_ID` as the manager account initially. When a real child ad account is linked, replace it with the child customer ID and keep `GOOGLE_ADS_LOGIN_CUSTOMER_ID` as the manager account ID.

## Demo Flow

1. Open `https://agenticgrowthlabs.com`.
2. Go to `Launch`.
3. Save or select a business.
4. Launch the agent loop to generate pages.
5. Go to `SEO Analytics`.
6. Click `Sync SEO metrics`.
7. Use the company filter to view the selected client's page performance.
8. Go to `Growth Suite`.
9. Select the correct company in `Authority target` before reviewing Backlink / Authority numbers.
10. Click `Run growth suite`.
11. Review six agent cards, integration readiness, client workspaces, reporting snapshot, and orchestration flow.
12. In the Google Ads command center, choose a campaign and daily budget.
13. Click `Draft Google Ads plan`.
14. Review headlines, keywords, final URL, status, and budget.
15. Click `Validate` to ask Google Ads API to validate the plan.
16. Click `Push paused campaign` only after owner approval.

## Production Notes

- The Growth Suite is safe to demo without all third-party secrets. Missing integrations show as pending instead of breaking the page.
- Every Growth Suite metric now carries a visible source label in the UI:
  - `Live Google Search Console`, `Live GA4`, or `Live Google Ads` means the value came from a connected Google API sync.
  - `Live DataForSEO` means the value came from the DataForSEO Backlinks Summary API.
  - `App DB` means the value is a count or record from the Marketing Agent database, such as generated pages, businesses, leads, campaigns, or workspaces.
  - `AI estimate` means the value was calculated by the OpenAI-powered agent and is not a direct Google metric.
  - `Demo fallback` means the app is using deterministic placeholder logic until the live provider has usable data for that metric.
  - `Configuration` means the value is a static app setting or governance rule.
- Google Ads campaign reads, validation, and push may remain pending until Google approves the account/API access level.
- Paid campaign push is intentionally approval-gated and creates paused Google Ads resources by default.
- Refresh recommendations are intentionally approval-based. Fully automatic publishing can be enabled later once clients approve governance rules.
- Do not commit service account JSON, developer tokens, API passwords, OAuth secrets, or refresh tokens to Git.
