# AWS Deployment Notes

This app is packaged for either Docker-based Elastic Beanstalk or a direct EC2 service.

## Required Secrets

- `OPENAI_API_KEY`: Your OpenAI key for research and page generation.
- `SECRET_KEY`: Long random string for production.
- `API_KEY`: Optional shared key for protected write APIs. Leave blank only for internal prototypes.

## Elastic Beanstalk

1. Create an Elastic Beanstalk Docker environment.
2. Set production environment variables in Elastic Beanstalk. Use your local `.env` only as a private reference; do not upload or commit it.
3. Attach an EBS volume or use a managed database for durable state.
4. If you keep SQLite for the first deployment, mount persistent storage at `/app/data`.
5. Prefer RDS Postgres for production traffic by setting `DATABASE_URL` to a SQLAlchemy Postgres URL.

Current production Elastic Beanstalk deployment:

```text
Application: marketing-agent-eb-app
Environment: marketing-agent-eb-prod
Region: ap-south-1
Elastic Beanstalk URL: http://marketing-agent-prod.ap-south-1.elasticbeanstalk.com
Production URL: https://agenticgrowthlabs.com
Alternate URLs: https://www.agenticgrowthlabs.com, https://app.agenticgrowthlabs.com
Database: marketing-agent-prod-postgres
S3 bucket: marketing-agent-prod-453732174568-ap-south-1
```

Current HTTPS routing:

```text
Route 53 hosted zone: agenticgrowthlabs.com / Z087564836Z3AAI4ODFFL
ACM certificate region: us-east-1
CloudFront distribution: EMF08K2YPZEP
CloudFront domain: d31dps223ry9uk.cloudfront.net
PUBLIC_BASE_URL: https://agenticgrowthlabs.com
```

Production PostgreSQL connection details and SQL inspection queries are documented in:

```text
docs/POSTGRES_QUERY_ARTIFACT.md
```

## S3

The current prototype does not require S3 because generated landing pages and leads are stored in the database.
Use S3 later for uploaded brand assets, generated images, exports, and audit archive snapshots.

## Production Checklist

- Keep HTTPS enabled through CloudFront and ACM.
- Set `API_KEY` and send it as `x-api-key` for admin write APIs.
- Restrict `ALLOWED_ORIGINS` to your dashboard domain.
- Move from SQLite to RDS Postgres before multi-instance scaling.
- Configure CloudWatch log retention and alarms for `/health`.
- Back up the database and export audit events regularly.

## Related Docs

- `docs/AWS_DEPLOYMENT_WALKTHROUGH.md`
- `docs/SECURITY_AND_COMPLIANCE.md`
- `docs/OPERATIONS_RUNBOOK.md`
