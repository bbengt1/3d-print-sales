# AI Insights

Read-only business intelligence for issue `#112`.

## What This Adds

- A dedicated `/insights` workspace instead of redirecting users into the reports stack.
- Admin-configurable LLM provider selection for `ChatGPT`, `Claude`, or `Grok`.
- A read-only insight summary flow grounded in app data from jobs, sales, inventory, materials, and printer status.
- A separate provider status endpoint so non-admin users can see whether Insights is available without exposing secrets.

## UX Intent

This slice follows the repo UX laws called out in `AGENTS.md`:

- Jakob's Law: `Insights` now behaves like a distinct analysis surface, not a disguised reports redirect.
- Hick's Law: operators start from one focused question plus a few guided presets instead of a crowded filter wall.
- Law of Common Region: AI interpretation is visually separated from source-of-truth evidence metrics.
- Doherty Threshold: the page shows immediate loading and generation feedback for async provider calls.

## Provider Configuration

Provider configuration lives in Admin Settings:

- `ai_provider`
- `ai_chatgpt_model`
- `ai_chatgpt_api_key`
- `ai_claude_model`
- `ai_claude_api_key`
- `ai_grok_model`
- `ai_grok_api_key`

Only admins can read or update `/api/v1/settings` because those records now include API secrets.

## API Surface

- `GET /api/v1/insights/status`
  - Authenticated
  - Returns the active provider, model, configured state, and explanatory note
  - Does not return API keys
- `POST /api/v1/insights/summary`
  - Authenticated
  - Accepts an optional focused natural-language question
  - Returns a read-only summary, recommendations, risks, suggested follow-up questions, and evidence metrics

## Safety Boundary

- Insights are read-only.
- No autonomous writes are performed.
- AI output is framed as recommendation, not source-of-truth record mutation.
- Business actions still require explicit operator action in the existing transactional workflows.

## Validation

- `python3 -m pytest backend/tests/test_api_settings.py backend/tests/test_api_insights.py -q`
- `cd frontend && npm test`
- `cd frontend && npm run build`
