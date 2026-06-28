# Models and Agents

## LLM Provider

The app uses OpenAI through:

```text
app/agents/llm.py
```

Settings:

```bash
OPENAI_ENABLED=true
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4.1-mini
```

## Recommended Model

Use:

```text
gpt-4.1-mini
```

Reason:

- Good enough for structured marketing generation.
- Lower cost than larger models.
- Fast for interactive dashboard workflows.

## Fallback Mode

If OpenAI is disabled or the API call fails:

- Research Agent returns deterministic demand signals.
- Content Agent returns deterministic landing page copy.
- Tests remain stable.

This behavior is intentional so local development does not depend on live model availability.

## Prompt Responsibilities

### Research Agent Prompt

Asks the model to return JSON with:

- `signals`
- `keyword`
- `intent`
- `priority_score`
- `rationale`

### Content Agent Prompt

Asks the model to return JSON with:

- `title`
- `hero`
- `sections`
- `cta`
- `seo`

## Output Normalization

LLM responses can vary. The app normalizes content through:

```text
app/core/content_formatting.py
```

This prevents structured objects from appearing in the UI as raw JSON or Python dictionary strings.

## Future Model Improvements

Recommended next steps:

- Add model call logging without storing sensitive prompt data.
- Add prompt versions.
- Add JSON schema validation for LLM responses.
- Add per-agent temperature controls.
- Add retry handling for transient OpenAI failures.
- Add cost tracking per campaign run.

