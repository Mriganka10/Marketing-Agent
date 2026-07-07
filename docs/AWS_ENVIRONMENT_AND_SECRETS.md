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

Elastic Beanstalk application:

```text
marketing-agent-eb-app
```

Elastic Beanstalk environment:

```text
marketing-agent-eb-prod
```

Elastic Beanstalk CNAME:

```text
marketing-agent-prod.ap-south-1.elasticbeanstalk.com
```

## Runtime

Platform:

```text
Docker running on 64bit Amazon Linux 2023
```

The app is a Dockerized FastAPI service. AWS Elastic Beanstalk runs the container.

## Deployment Script

Main deployment file:

```text
deploy/deploy_marketing_agent_eb.py
```

What it does:

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

Deployment script reads from:

```text
/marketing-agent/prod
```

Expected SSM parameters include:

```text
/marketing-agent/prod/database-url
/marketing-agent/prod/openai-api-key
/marketing-agent/prod/openai-model
/marketing-agent/prod/secret-key
/marketing-agent/prod/s3-bucket
/marketing-agent/prod/ga4-measurement-id
/marketing-agent/prod/ga4-property-id
/marketing-agent/prod/google-search-console-site-url
/marketing-agent/prod/google-service-account-json
/marketing-agent/prod/dataforseo-enabled
/marketing-agent/prod/dataforseo-login
/marketing-agent/prod/dataforseo-password
/marketing-agent/prod/google-ads-enabled
/marketing-agent/prod/google-ads-developer-token
/marketing-agent/prod/google-ads-client-id
/marketing-agent/prod/google-ads-client-secret
/marketing-agent/prod/google-ads-refresh-token
/marketing-agent/prod/google-ads-login-customer-id
/marketing-agent/prod/google-ads-customer-id
/marketing-agent/prod/google-ads-api-version
```

## Verification Commands

Health:

```bash
curl -sS https://agenticgrowthlabs.com/health
```

Growth Suite:

```bash
curl -sS https://agenticgrowthlabs.com/api/growth/overview
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

If values are changed directly in Elastic Beanstalk Configuration:

1. Save changes.
2. Wait for environment update to complete.
3. Confirm health is `Ok`.
4. Run `/health`.

If values are changed in SSM and not directly in EB:

1. Update SSM parameter.
2. Rerun deployment script or update EB environment so the container receives the new value.
3. Confirm `/health`.

## Google Server And Play Store Clarification

The app is not hosted on Google servers.

It is hosted on AWS.

It is not currently a Play Store mobile app.

It is a responsive web app that can be opened on mobile browser:

```text
https://agenticgrowthlabs.com
```

To make it downloadable from Google Play Store, a separate Android app or Progressive Web App packaging flow would be required. That is not part of the current deployment.

