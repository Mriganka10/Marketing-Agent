# AWS Deployment Notes

This app is packaged for either Docker-based Elastic Beanstalk or a direct EC2 service.

## Required Secrets

- `OPENAI_API_KEY`: Your OpenAI key for research and page generation.
- `SECRET_KEY`: Long random string for production.
- `API_KEY`: Optional shared key for protected write APIs. Leave blank only for internal prototypes.

## Elastic Beanstalk

1. Create an Elastic Beanstalk Docker environment.
2. Store application settings and secrets under `/marketing-agent/prod` in SSM Parameter Store.
3. Set only the non-secret runtime bootstrap values in Elastic Beanstalk:

   ```text
   AWS_REGION=ap-south-1
   SSM_ENABLED=true
   SSM_PARAMETER_PATH=/marketing-agent/prod
   SSM_FAIL_FAST=true
   SSM_REQUIRED_PARAMETERS=database-url,secret-key
   ```

   The application retrieves all parameters recursively with decryption during startup. Required
   parameters must exist and be non-empty. SSM values
   override same-named EB environment values, so the runtime never depends on copied secret values.
4. Attach an EBS volume or use a managed database for durable state.
5. If you keep SQLite for the first deployment, mount persistent storage at `/app/data`.
6. Prefer RDS Postgres for production traffic by storing `database-url` as a SecureString.

The EC2 instance role receives a dedicated inline policy named
`marketing-agent-ssm-parameter-read`. It grants only `ssm:GetParametersByPath` on:

```text
arn:aws:ssm:ap-south-1:<account-id>:parameter/marketing-agent/prod/*
```

SecureString decryption is limited to calls routed through the regional SSM service. Set
`SSM_KMS_KEY_ARN` while running the deployment script to restrict `kms:Decrypt` to a customer-managed
key; otherwise the policy uses `*` with the `kms:ViaService` condition for compatibility with the
AWS-managed SSM key. The deployment script applies the policy idempotently to
`marketing-agent-eb-ec2-role` and removes legacy secret-bearing EB environment entries.

Verify the deployed permission with:

```bash
aws iam get-role-policy \
  --role-name marketing-agent-eb-ec2-role \
  --policy-name marketing-agent-ssm-parameter-read
```

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
