# Frontend Design System

This document records the maintained frontend color and accessibility rules for the app. Use it when changing shared UI primitives, theme tokens, report charts, or operational status surfaces.

## Light Mode Color Rules

Light mode uses high-contrast semantic tokens from `frontend/src/index.css`. Do not introduce pale status colors that disappear into white or near-white surfaces.

| Purpose | Token family | Light foreground | Light surface | Notes |
| --- | --- | --- | --- | --- |
| Primary action / info | `primary`, `info` | `#005ea8` | `#c8ddf2` | Operational blue with readable text and visible borders. |
| Success / complete | `success` | `#006b5b` | `#cfe7df` | Blue-green, selected to reduce red/green confusion compared with bright green. |
| Warning / attention | `warning` | `#7a4a00` | `#ead3a6` | Brown-amber, not pale yellow, so low-stock and paused states remain visible. |
| Error / destructive | `destructive` | `#b42318` | `#f1cfcb` | Vermillion red with a stronger border token. |
| Neutral | `muted`, `border`, `foreground` | `#0f172a` / `#475569` | `#f1f5f9` | Use for non-semantic grouping and quiet secondary text. |

## Component Guidance

- Prefer shared primitives before page-specific colors: `StatusBadge`, `Callout`, `AppToaster`, `KPIStrip`, and chart helpers in `frontend/src/components/charts/ChartTooltip.tsx`.
- Use `text-success`, `text-warning`, `text-info`, and `text-destructive` for semantic text. Avoid direct `text-emerald-*`, `text-amber-*`, `text-sky-*`, and `text-red-*` classes for operational states.
- Use semantic surface tokens such as `bg-success-surface` and `border-success-border` for badges, banners, and panels. Do not use `bg-*-50` for meaningful light-mode statuses.
- Do not communicate critical meaning through color alone. Pair colors with labels, icons, or status text so red/green color vision differences do not block understanding.
- Report charts should use `chartCategoricalPalette` and always include legends, labels, or table context for series meaning.

## Validation

Before merging frontend color changes:

- Run `cd frontend && npm run build`.
- Check representative light-mode badges, callouts, toasts, focus rings, chart series, and dense tables.
- Verify normal text on semantic foreground colors has at least 4.5:1 contrast against the page or component background.
- Verify meaningful non-text indicators such as borders, dots, and focus rings have at least 3:1 contrast where practical.
- Review red/green paired states with labels or icons visible, not hue alone.
