# AWS Deployment Walkthrough

Last updated: 10 September 2026.

```text
agenticgrowthlabs.com -> CloudFront -> shared ALB -> Marketing ECS web
                                                        |
daily 08:30 Asia/Kolkata -> EventBridge -> SQS -> ECS worker -> DLQ
                                                        |
                                        dedicated database/role + S3/SSM
```

CloudFront preserves the domain and TLS behavior. A private origin header selects the application's target group. Interactive APIs and public landing pages stay in the web service. The scheduled Google metrics sync no longer depends on an in-process thread: EventBridge supplies timing, SQS supplies buffering/retry, and the worker executes the sync.

`run_google_sync_once` re-raises failures after audit logging, so the worker does not acknowledge failed work. Review the DLQ cause before redrive. Scale web tasks for request load and workers from queue depth/age.

Release acceptance requires healthy ECS targets and checks for `/health`, protected writes, generated/public pages, leads, approval/publish, dashboards, Google integration status, and a queue-driven sync. The paused Elastic Beanstalk stack is rollback history only.
