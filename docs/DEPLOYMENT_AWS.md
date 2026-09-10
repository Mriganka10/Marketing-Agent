# AWS Production Deployment

Last updated: 10 September 2026.

`agenticgrowthlabs.com` remains live through CloudFront -> shared ALB -> isolated Marketing Agent ECS web service. A separate ECS worker consumes the application's SQS queue. Production Google synchronization is triggered by EventBridge Scheduler at 08:30 `Asia/Kolkata`.

The application shares the ALB, ARM ECS capacity, and physical RDS instance with the other applications. It retains independent target group, services/task roles, secrets/SSM path, queue/DLQ, logical PostgreSQL database and role, and S3 namespace.

```text
GOOGLE_SYNC_SCHEDULER_BACKEND=eventbridge
WORKER_QUEUE_URL=<queue-url>
SERVICE_MODE=worker                 # worker task only
PUBLIC_BASE_URL=https://agenticgrowthlabs.com
SSM_ENABLED=true
SSM_PARAMETER_PATH=/marketing-agent/prod
```

Keep database, OpenAI, API key, Google, email, and third-party credentials in SSM/Secrets Manager. The ECS task role needs least-privilege access only to this application's parameters, queue, S3 namespace, logs, and required KMS keys.

Build one immutable ARM-compatible image and deploy its digest to both task definitions. Update the worker before the web service, wait for stability, then test health, protected APIs, campaign generation, public pages, lead capture, approval/publish, analytics, and one queued Google sync. Monitor ALB errors, ECS restarts, EventBridge failures, queue age/DLQ, RDS, and sync audit records.

Rollback uses preceding ECS task definitions. The old Elastic Beanstalk environment is paused for a temporary 7–14 day rollback window and is not the active runtime.

See [deployment walkthrough](AWS_DEPLOYMENT_WALKTHROUGH.md), [environment and secrets](AWS_ENVIRONMENT_AND_SECRETS.md), [operations](OPERATIONS_RUNBOOK.md), and [code walkthrough](CODE_WALKTHROUGH.md).
