# Local Setup

## Prerequisites

- macOS terminal or equivalent shell.
- Git.
- Python 3.11 or 3.12.
- Existing `.env` file for local secrets and settings.

## Recommended Local Commands

Use the existing virtual environment:

```bash
cd "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Marketing-Agent"
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8015
```

Open:

```text
http://127.0.0.1:8015
```

## Recreate the Virtual Environment

If `.venv` breaks, recreate it with the stable Python runtime that has worked on this machine:

```bash
cd "/Users/user/Library/Mobile Documents/com~apple~CloudDocs/Marketing-Agent"
rm -rf .venv
/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8015
```

## Local Environment File

Use `.env` for local configuration. It is ignored by git.

Minimum local values:

```bash
APP_NAME="Marketing Agent"
ENVIRONMENT=local
DATABASE_URL=sqlite:///./data/marketing_agent.db
OPENAI_ENABLED=true
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-5.5
PUBLIC_BASE_URL=http://localhost:8015
ALLOWED_ORIGINS=["*"]
```

If `DATABASE_URL` is blank, the app falls back to SQLite:

```text
sqlite:///./data/marketing_agent.db
```

## Install Dependencies

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

## Run Tests

```bash
source .venv/bin/activate
python -m pytest
python -m ruff check app tests
```

## Common Issues

### Address already in use

Another server is already using the port.

```bash
lsof -ti :8015 | xargs kill -9
python -m uvicorn app.main:app --reload --port 8015
```

Or run on another port:

```bash
python -m uvicorn app.main:app --reload --port 8016
```

### `python` command not found

Activate the virtual environment:

```bash
source .venv/bin/activate
```

### Broken Homebrew Python

If Homebrew Python fails with `platform.mac_ver() returned an empty value`, use the bundled Python command shown in the virtual environment recreation section.

