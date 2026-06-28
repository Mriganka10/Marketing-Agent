# AWS Deployment Walkthrough

## Recommended First Production Shape

For the first cloud deployment:

- Elastic Beanstalk Docker environment.
- Single EC2 instance.
- EBS-backed persistent `/app/data` if using SQLite.
- CloudWatch logs.
- HTTPS through Elastic Load Balancer.

For a more durable production setup:

- Elastic Beanstalk Docker environment.
- RDS Postgres.
- S3 for future assets and exports.
- AWS Secrets Manager or EB environment variables for secrets.

## 1. Prepare Local Repo

```bash
python -m pytest
python -m ruff check app tests
docker build -t marketing-agent .
```

## 2. Configure Environment Variables

Set these in Elastic Beanstalk:

```bash
APP_NAME=Marketing Agent
ENVIRONMENT=production
SECRET_KEY=long-random-secret
API_KEY=admin-write-api-key
DATABASE_URL=sqlite:///./data/marketing_agent.db
OPENAI_ENABLED=true
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4.1-mini
PUBLIC_BASE_URL=https://your-domain.example
ALLOWED_ORIGINS=["https://your-domain.example"]
```

For RDS Postgres:

```bash
DATABASE_URL=postgresql+psycopg://user:password@host:5432/marketing_agent
```

The current dependencies do not include a Postgres driver. Add one before switching to Postgres:

```text
psycopg[binary]
```

## 3. Create Elastic Beanstalk Environment

Choose:

- Platform: Docker
- Application load balancer if using HTTPS/custom domain
- Instance type: small general-purpose instance for first deployment

## 4. Persistent Storage

If using SQLite, attach EBS and mount it so `/app/data` persists across deployments.

For production traffic, prefer RDS Postgres instead of SQLite.

## 5. Deploy

Zip or deploy the repository with:

- `Dockerfile`
- `Procfile`
- `app/`
- `pyproject.toml`
- `README.md`
- `.platform/`

Do not include:

- `.env`
- `.venv`
- `data/`

## 6. Verify

After deployment:

```bash
curl https://your-domain.example/health
```

Then manually check:

- Dashboard loads.
- Business profile can be saved.
- Campaign run completes.
- Public page opens.
- Lead capture works.
- Audit events are created.

## 7. Post-Deployment Hardening

- Add HTTPS.
- Restrict CORS.
- Set `API_KEY`.
- Enable CloudWatch retention.
- Configure backups.
- Rotate secrets after initial setup.
- Add rate limiting before public launch.

