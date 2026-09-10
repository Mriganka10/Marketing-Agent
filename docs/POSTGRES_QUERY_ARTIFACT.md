# PostgreSQL Query Artifact

This document contains production-safe commands and SQL queries for inspecting the Marketing Agent PostgreSQL database.

Do not commit database passwords, OpenAI keys, or decrypted connection strings to Git. The commands below retrieve the live connection string inside the AWS environment when needed.

## Production Database

AWS region:

```text
ap-south-1
```

Active runtime:

```text
isolated Marketing Agent ECS web/worker services
```

RDS topology:

```text
shared protected PostgreSQL instance; dedicated Marketing database and role
```

RDS endpoint:

```text
marketing-agent-prod-postgres.c7yu6kk6ytyl.ap-south-1.rds.amazonaws.com
```

SSM secure parameter path for the connection URL:

```text
/marketing-agent/prod/database-url
```

Connection URL format:

```text
postgresql+psycopg://<username>:<password>@marketing-agent-prod-postgres.c7yu6kk6ytyl.ap-south-1.rds.amazonaws.com:5432/<database>
```

## Get the Connection URL from AWS CLI

Run this from a machine or CloudShell session that has permission to read the secure SSM parameter:

```bash
aws ssm get-parameter \
  --region ap-south-1 \
  --name /marketing-agent/prod/database-url \
  --with-decryption \
  --query Parameter.Value \
  --output text
```

## Get the Connection URL from an ECS Task

Use ECS Exec only from an authorized operator session and only when audit policy permits it:

```bash
aws ecs execute-command --cluster <cluster> --task <task-id> --container <container> \
  --interactive --command "/bin/sh"
```

Inside the task, use an approved database client. Avoid printing a decrypted connection URL into
terminal history; prefer IAM-controlled secret retrieval and audit the session.

## Connect with psql

Use a short-lived administrative task or approved bastion in the VPC with the PostgreSQL client.
Do not modify a running application container to install tools.

```bash
psql "postgresql://<app-role>:<secret>@<shared-rds-endpoint>:5432/<marketing-db>"
```

Retrieve the password at execution time from the approved secure store. Do not export or paste it
into shared logs, tickets, screenshots, or this repository.

## Table List

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected tables:

```text
audit_events
business_profiles
campaigns
demand_signals
landing_pages
leads
refresh_recommendations
```

## Dashboard Summary Query

This matches the main dashboard counters.

```sql
SELECT
  (SELECT COUNT(*) FROM business_profiles) AS businesses,
  (SELECT COUNT(*) FROM campaigns) AS campaigns,
  (SELECT COUNT(*) FROM landing_pages) AS pages,
  (SELECT COUNT(*) FROM leads) AS leads,
  COALESCE((SELECT SUM(visits) FROM landing_pages), 0) AS visits,
  COALESCE((SELECT SUM(conversions) FROM landing_pages), 0) AS conversions,
  CASE
    WHEN COALESCE((SELECT SUM(visits) FROM landing_pages), 0) = 0 THEN 0
    ELSE ROUND(
      (
        COALESCE((SELECT SUM(conversions) FROM landing_pages), 0)::numeric
        / COALESCE((SELECT SUM(visits) FROM landing_pages), 0)::numeric
      ) * 100,
      2
    )
  END AS conversion_rate_percent;
```

## Recent Leads

```sql
SELECT
  l.id,
  l.created_at,
  l.name,
  l.email,
  l.company,
  l.score,
  l.status,
  l.source,
  c.name AS campaign_name,
  p.title AS page_title,
  p.slug AS page_slug
FROM leads l
JOIN campaigns c ON c.id = l.campaign_id
LEFT JOIN landing_pages p ON p.id = l.page_id
ORDER BY l.created_at DESC
LIMIT 50;
```

## Lead Score Explanation Query

This helps validate why a lead received a score.

```sql
SELECT
  id,
  created_at,
  name,
  email,
  company,
  LENGTH(COALESCE(message, '')) AS message_length,
  CASE WHEN company IS NOT NULL AND company <> '' THEN 20 ELSE 0 END AS company_bonus,
  CASE WHEN LENGTH(COALESCE(message, '')) > 40 THEN 25 ELSE 0 END AS message_bonus,
  CASE
    WHEN LOWER(SPLIT_PART(email, '@', 2)) NOT IN ('gmail.com', 'yahoo.com', 'hotmail.com') THEN 20
    ELSE 0
  END AS business_email_bonus,
  score,
  status
FROM leads
ORDER BY created_at DESC
LIMIT 50;
```

## Leads by Status

```sql
SELECT
  status,
  COUNT(*) AS total_leads,
  ROUND(AVG(score)::numeric, 2) AS average_score,
  MAX(score) AS max_score,
  MIN(score) AS min_score
FROM leads
GROUP BY status
ORDER BY total_leads DESC;
```

## Landing Page Performance

```sql
SELECT
  p.id,
  p.created_at,
  p.status,
  p.title,
  p.slug,
  p.visits,
  p.conversions,
  CASE
    WHEN p.visits = 0 THEN 0
    ELSE ROUND((p.conversions::numeric / p.visits::numeric) * 100, 2)
  END AS conversion_rate_percent,
  c.name AS campaign_name
FROM landing_pages p
JOIN campaigns c ON c.id = p.campaign_id
ORDER BY p.created_at DESC;
```

## Campaign Performance

```sql
SELECT
  c.id,
  c.name,
  c.status,
  c.target_region,
  b.name AS business_name,
  COUNT(DISTINCT p.id) AS pages,
  COALESCE(SUM(p.visits), 0) AS visits,
  COALESCE(SUM(p.conversions), 0) AS conversions,
  COUNT(DISTINCT l.id) AS leads,
  CASE
    WHEN COALESCE(SUM(p.visits), 0) = 0 THEN 0
    ELSE ROUND((COALESCE(SUM(p.conversions), 0)::numeric / SUM(p.visits)::numeric) * 100, 2)
  END AS conversion_rate_percent
FROM campaigns c
JOIN business_profiles b ON b.id = c.business_id
LEFT JOIN landing_pages p ON p.campaign_id = c.id
LEFT JOIN leads l ON l.campaign_id = c.id
GROUP BY c.id, c.name, c.status, c.target_region, b.name
ORDER BY c.created_at DESC;
```

## Demand Signals

```sql
SELECT
  ds.created_at,
  b.name AS business_name,
  c.name AS campaign_name,
  ds.keyword,
  ds.intent,
  ds.region,
  ds.priority_score,
  ds.rationale
FROM demand_signals ds
JOIN campaigns c ON c.id = ds.campaign_id
JOIN business_profiles b ON b.id = c.business_id
ORDER BY ds.priority_score DESC, ds.created_at DESC;
```

## Refresh Recommendations

```sql
SELECT
  rr.created_at,
  rr.severity,
  rr.status,
  rr.recommendation,
  rr.expected_impact,
  c.name AS campaign_name,
  p.title AS page_title
FROM refresh_recommendations rr
JOIN campaigns c ON c.id = rr.campaign_id
LEFT JOIN landing_pages p ON p.id = rr.page_id
ORDER BY rr.created_at DESC;
```

## Audit Trail

```sql
SELECT
  created_at,
  actor,
  action,
  entity_type,
  entity_id,
  event_metadata
FROM audit_events
ORDER BY created_at DESC
LIMIT 100;
```

## Audit Events by Actor

```sql
SELECT
  actor,
  action,
  COUNT(*) AS event_count,
  MAX(created_at) AS latest_event_at
FROM audit_events
GROUP BY actor, action
ORDER BY latest_event_at DESC;
```

## Business Profiles

```sql
SELECT
  id,
  created_at,
  updated_at,
  name,
  website,
  industry,
  audience,
  value_proposition,
  offers,
  competitors,
  tone
FROM business_profiles
ORDER BY created_at DESC;
```

## Full Campaign Drilldown

Replace `<campaign_id>` before running.

```sql
SELECT
  c.id AS campaign_id,
  c.name AS campaign_name,
  c.goal,
  c.target_region,
  c.status AS campaign_status,
  b.name AS business_name,
  p.id AS page_id,
  p.title AS page_title,
  p.slug,
  p.status AS page_status,
  p.visits,
  p.conversions,
  l.id AS lead_id,
  l.name AS lead_name,
  l.email AS lead_email,
  l.company AS lead_company,
  l.score AS lead_score,
  l.status AS lead_status
FROM campaigns c
JOIN business_profiles b ON b.id = c.business_id
LEFT JOIN landing_pages p ON p.campaign_id = c.id
LEFT JOIN leads l ON l.campaign_id = c.id AND l.page_id = p.id
WHERE c.id = '<campaign_id>'
ORDER BY p.created_at DESC, l.created_at DESC;
```
