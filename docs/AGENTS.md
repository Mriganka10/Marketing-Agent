# Agents

## Agent Loop

The product loop is:

Understand business -> find demand -> create pages -> capture leads -> improve pages.

## Business Memory Agent

File: `app/agents/business_memory.py`

Responsibilities:

- Store business profile.
- Store industry, audience, positioning, offers, competitors, and tone.
- Create campaigns connected to a business.
- Write audit events for profile and campaign creation.

Inputs:

- Business profile form.
- Campaign form.

Outputs:

- `BusinessProfile`
- `Campaign`
- Audit events.

## Research Agent

File: `app/agents/research.py`

Responsibilities:

- Generate demand signals for a campaign.
- Identify keyword ideas, buyer intent, priority score, and rationale.
- Use OpenAI when configured.
- Fall back to deterministic demand signals when OpenAI is unavailable.

Inputs:

- Business profile.
- Campaign goal.
- Target region.

Outputs:

- `DemandSignal` records.

## Content/Page Creation Agent

File: `app/agents/content.py`

Responsibilities:

- Generate landing page title, hero copy, page sections, CTA, and SEO metadata.
- Create unique slugs.
- Publish or draft pages.
- Normalize structured LLM output into readable prose.

Inputs:

- Business profile.
- Campaign.
- Demand signals.

Outputs:

- `LandingPage` records.

Important support file:

- `app/core/content_formatting.py` repairs and normalizes structured strings such as `{"heading": "...", "body": "..."}` into readable copy.

## Lead Capture Agent

File: `app/agents/lead_capture.py`

Responsibilities:

- Capture public landing page form submissions.
- Score leads.
- Mark leads as `qualified` or `new`.
- Increment landing page conversions.
- Write lead audit events.

Lead scoring:

- Starts at 35.
- Adds score for company presence.
- Adds score for detailed message.
- Adds score for non-free email domain.

Detailed scoring and dashboard conversion rules:

```text
docs/LEAD_SCORING_AND_CONVERSION.md
```

## Analytics/Refresh Agent

File: `app/agents/analytics_refresh.py`

Responsibilities:

- Review landing page visits and conversions.
- Create refresh recommendations.
- Prioritize pages with low traffic, low conversion, or scaling opportunity.

Outputs:

- `RefreshRecommendation` records.

## Orchestrator

File: `app/agents/orchestrator.py`

Responsibilities:

- Coordinate the Research, Content, and Analytics agents.
- Run the complete campaign generation flow.

Primary route:

```text
POST /api/runs
```
