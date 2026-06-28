# Testing and QA

## Test Commands

```bash
source .venv/bin/activate
python -m pytest
python -m ruff check app tests
```

## Current Test Coverage

Tests cover:

- Health endpoint.
- Dashboard root page.
- Business profile creation.
- Campaign creation.
- Full agent loop execution.
- Landing page publishing.
- Public landing page render.
- Lead capture and scoring.
- Dashboard metrics.
- Structured LLM content normalization.
- Existing page content repair through `/api/pages`.

## Manual QA Checklist

1. Start the app:

   ```bash
   python -m uvicorn app.main:app --reload --port 8015
   ```

2. Open:

   ```text
   http://127.0.0.1:8015
   ```

3. Confirm dashboard loads.
4. Save a business profile.
5. Launch a campaign.
6. Confirm generated pages appear.
7. Open a generated page.
8. Submit a test lead.
9. Confirm lead appears in the dashboard.
10. Confirm recommendations appear.
11. Confirm audit events appear.

## UI QA

Check:

- Desktop layout has no horizontal overflow.
- Mobile layout stacks cleanly.
- Generated page cards show human-readable prose.
- Public landing pages show readable sections and CTA.
- Buttons and forms fit their containers.

## Known Warning

FastAPI TestClient currently emits a Starlette/httpx deprecation warning. It does not block tests.

## Before Deployment

Run:

```bash
python -m pytest
python -m ruff check app tests
docker build -t marketing-agent .
```

