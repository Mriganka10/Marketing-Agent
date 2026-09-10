# AWS Environment And Secrets

This document explains where production runs, where secrets are stored, and which values the owner must maintain.

## Production Hosting

Production domain:

```text
https://agenticgrowthlabs.com
```

AWS region:

```text
ap-south-1
```

Active hosting: CloudFront -> shared ALB -> isolated ECS web service, with EventBridge -> SQS ->
isolated ECS worker for the daily Google sync.

## Runtime

The app is a Dockerized FastAPI service. The same ARM-compatible image runs in ECS web and worker
modes on shared EC2 capacity.

## Legacy Deployment Script

Main deployment file:

```text
deploy/deploy_marketing_agent_eb.py
```

`deploy/deploy_marketing_agent_eb.py` documents the former Elastic Beanstalk release path. It is
retained only for rollback history during the temporary observation window and must not be used
for a normal production deployment. Historically it:

- builds the deployment zip;
- uploads the source bundle to S3;
- creates/updates Elastic Beanstalk application version;
- sets Elastic Beanstalk environment options;
- reads secret values from AWS SSM Parameter Store where configured;
- updates the running production environment.

## Required Core Environment Values

```text
APP_NAME=Marketing Agent
ENVIRONMENT=production
SECRET_KEY=<secret>
DATABASE_URL=<postgres-url>
DATA_DIR=/app/data
PUBLIC_BASE_URL=https://agenticgrowthlabs.com
```

## OpenAI Values

```text
OPENAI_ENABLED=true
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5.5
OPENAI_REASONING_EFFORT=medium
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

## Google SEO Values

```text
GA4_MEASUREMENT_ID=G-KZ3N4G2S20
GA4_PROPERTY_ID=544328945
GOOGLE_SEARCH_CONSOLE_SITE_URL=sc-domain:agenticgrowthlabs.com
GOOGLE_SERVICE_ACCOUNT_JSON=<service-account-json-secret>
```

## DataForSEO Values

```text
DATAFORSEO_ENABLED=true
DATAFORSEO_LOGIN=<secret>
DATAFORSEO_PASSWORD=<secret>
```

These values enable two checks:

- account readiness through DataForSEO user data;
- live Backlink / Authority Agent metrics through the DataForSEO Backlinks Summary API.

The Growth Suite `Authority target` dropdown chooses which business website is checked. The backend defaults to the first real business website and avoids placeholder domains such as `example.com`, `localhost`, and `127.0.0.1` unless the owner explicitly selects that business.

If account readiness is green but backlink metrics still show `Demo fallback`, the credentials are present but the backlinks endpoint is returning an authorization, balance, or data-access error. In that case, verify the DataForSEO account balance and API access, then run the Growth Suite again.

## Google Ads Values

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

## SSM Parameter Path

The application reads directly from this path at every process startup:

```text
/kairoz/production/marketing
```

Expected SSM parameters include:

```text
/kairoz/production/marketing/database-url
/kairoz/production/marketing/openai-api-key
/kairoz/production/marketing/openai-model
/kairoz/production/marketing/secret-key
/kairoz/production/marketing/api-key
/kairoz/production/marketing/s3-bucket
/kairoz/production/marketing/ga4-measurement-id
/kairoz/production/marketing/ga4-property-id
/kairoz/production/marketing/google-search-console-site-url
/kairoz/production/marketing/google-service-account-json
/kairoz/production/marketing/dataforseo-enabled
/kairoz/production/marketing/dataforseo-login
/kairoz/production/marketing/dataforseo-password
/kairoz/production/marketing/google-ads-enabled
/kairoz/production/marketing/google-ads-developer-token
/kairoz/production/marketing/google-ads-client-id
/kairoz/production/marketing/google-ads-client-secret
/kairoz/production/marketing/google-ads-refresh-token
/kairoz/production/marketing/google-ads-login-customer-id
/kairoz/production/marketing/google-ads-customer-id
/kairoz/production/marketing/google-ads-api-version
```

Recommended owner practice:

- store long-lived production secrets in SSM SecureString parameters;
- keep only `AWS_REGION`, `SSM_ENABLED`, `SSM_PARAMETER_PATH`, `SSM_FAIL_FAST`, and
  `SSM_REQUIRED_PARAMETERS` as ECS bootstrap values;
- SSM parameters take precedence over same-named environment values;
- keep `SSM_FAIL_FAST=true` in production so missing IAM access, missing paths, or AWS failures stop startup instead of silently using stale values;
- parameter names map from kebab case to application setting names, for example `openai-api-key` becomes `OPENAI_API_KEY` and `database-url` becomes `DATABASE_URL`.

## Verification Commands

Health:

```bash
curl -sS https://agenticgrowthlabs.com/health
```

Growth Suite:

```bash
curl -sS https://agenticgrowthlabs.com/api/growth/overview
```

Paid ad plans:

```bash
curl -sS https://agenticgrowthlabs.com/api/ads/plans
```

SEO integrations:

```bash
curl -sS https://agenticgrowthlabs.com/api/seo/integrations
```

Sitemap:

```bash
curl -sS https://agenticgrowthlabs.com/sitemap.xml
```

Robots:

```bash
curl -sS https://agenticgrowthlabs.com/robots.txt
```

## Owner Secret Rules

Never commit these:

- `.env`;
- Google service account JSON;
- Google Ads developer token;
- OAuth client secret;
- OAuth refresh token;
- DataForSEO password;
- OpenAI key;
- database URL if it includes password.

If a secret is exposed in a screenshot or chat, rotate it.

## After Changing AWS Values

If ECS bootstrap values are changed:

1. Save changes.
2. Register a new task-definition revision and update both affected services.
3. Wait for ECS services and ALB targets to become healthy.
4. Run `/health`.

Google Ads note:

After rotating Google Ads values, force a new ECS deployment so new processes reload settings. No
new image is required for a secret-only change.

If values are changed in SSM:

1. Update SSM parameter.
2. Restart or redeploy the application process. Runtime settings are loaded once per process and cached.
3. Confirm `/health`.

`/health` reports `ssm_runtime_loading` and `ssm_parameters_loaded` without exposing parameter names
or decrypted values.

The Marketing ECS task role uses a dedicated SSM read policy. Its SSM resource is restricted to
`parameter/kairoz/production/marketing/*`; it does not grant account-wide Parameter Store reads.

## Google Server And Play Store Clarification

The app is not hosted on Google servers.

It is hosted on AWS.

It is not currently a Play Store mobile app.

It is a responsive web app that can be opened on mobile browser:

```text
https://agenticgrowthlabs.com
```

To make it downloadable from Google Play Store, a separate Android app or Progressive Web App packaging flow would be required. That is not part of the current deployment.
