# Operations Runbook

## Start Locally

```bash
cd "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Marketing-Agent"
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8015
```

## Stop Local Server

Press `Ctrl+C` in the terminal running Uvicorn.

If the terminal is gone:

```bash
lsof -ti :8015 | xargs kill -9
```

## Check Health

```bash
curl http://127.0.0.1:8015/health
```

Healthy response:

```json
{
  "status": "ok",
  "service": "Marketing Agent",
  "environment": "local",
  "openai_configured": true
}
```

## Reset Local Data

This deletes local app data.

```bash
rm -f data/marketing_agent.db
python -m uvicorn app.main:app --reload --port 8015
```

The database tables are recreated at startup.

## Backup Local SQLite

```bash
mkdir -p backups
cp data/marketing_agent.db "backups/marketing_agent_$(date +%Y%m%d_%H%M%S).db"
```

## Common Incidents

### App will not start because port is in use

```bash
lsof -ti :8015 | xargs kill -9
python -m uvicorn app.main:app --reload --port 8015
```

### App will not start because database URL is invalid

Check `.env`:

```bash
grep DATABASE_URL .env
```

Set:

```bash
DATABASE_URL=sqlite:///./data/marketing_agent.db
```

### OpenAI calls fail

Check:

```bash
grep OPENAI_MODEL .env
grep OPENAI_ENABLED .env
```

Use:

```bash
OPENAI_ENABLED=true
OPENAI_MODEL=gpt-5.5
```

If key or model access fails, the app falls back to deterministic generation.

### Generated text looks like JSON

This should be repaired by `app/core/content_formatting.py` and the `/api/pages` repair path. If it appears again:

1. Run tests.
2. Open `/api/pages`.
3. Check LLM response shape in the Content/Page Creation Agent.

## Production Monitoring

Monitor:

- `/health`
- Uvicorn process status.
- Error logs.
- Database disk usage.
- Lead capture volume.
- LLM failures.
- Conversion rate.

Production health check:

```bash
curl https://agenticgrowthlabs.com/health
```

Production database inspection:

```text
docs/POSTGRES_QUERY_ARTIFACT.md
```

Lead score and conversion explanation:

```text
docs/LEAD_SCORING_AND_CONVERSION.md
```
