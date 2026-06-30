# Security and Compliance

## Secrets

Secrets belong in `.env` locally or cloud environment variables in production.

Never commit:

- `OPENAI_API_KEY`
- `SECRET_KEY`
- `API_KEY`
- SMTP credentials
- AWS credentials
- Database passwords

## OpenAI Key

If a key is pasted into chat, screenshots, or a committed file, rotate it in the OpenAI dashboard.

## API Protection

Admin write routes are protected when `API_KEY` is configured.

Header:

```http
x-api-key: your-api-key
```

Routes protected by `API_KEY` include:

- `POST /api/businesses`
- `POST /api/campaigns`
- `POST /api/runs`
- `POST /api/campaigns/{campaign_id}/refresh`

Lead capture remains public:

```http
POST /api/leads
```

## CORS

Local default:

```text
ALLOWED_ORIGINS=["*"]
```

Production recommendation:

Set `ALLOWED_ORIGINS` to the exact dashboard and public site domains.

## Data Stored

The app stores:

- Business positioning.
- Landing page content.
- Lead contact information.
- Lead messages.
- Audit events.

Treat lead data as sensitive business data.

## Deployment Security Checklist

- Use HTTPS through Elastic Load Balancer or reverse proxy.
- Set a strong `SECRET_KEY`.
- Set `API_KEY` for admin write routes.
- Restrict CORS.
- Avoid exposing SQLite files publicly.
- Use RDS credentials through environment variables or AWS Secrets Manager.
- Enable CloudWatch logs.
- Rotate OpenAI and AWS keys periodically.

## Current Limitations

- No full user login system yet.
- No per-user role permissions in the dashboard.
- No PII redaction in audit metadata.
- No rate limiting on public lead capture.

Recommended next security work:

- Add authentication.
- Add CSRF/rate protection for public forms.
- Add IP-based throttling.
- Add structured secret management for AWS.

