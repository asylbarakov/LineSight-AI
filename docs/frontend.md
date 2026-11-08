# Frontend features and validation

The existing Next.js workflow remains login → MP4 upload → worker processing →
findings → engineer review → PDF. Real requests use the shared API client;
authentication, inspection and PDF endpoints were not replaced.

## Interface

- Near-black/light themes use shared CSS/Tailwind tokens, persisted theme/navigation
  preferences, accessible controls and mobile navigation.
- Proxima Nova uses locally installed faces only. Bundled licensed Onest covers
  unavailable fonts and Kazakh glyphs; proprietary font files are not redistributed.
  Body/table typography stays 16px.
- Dashboard has exactly three authoritative KPIs, recent inspections, shared search
  and status filters, actual upload trends and explicit unavailable aggregates.
- Upload controls remain mounted inside a disclosure, preserving input/progress.
- Video review keeps independently collapsible findings, exact timestamp selection,
  priority/type icon markers, overlapping-event groups and synchronized cards.
  Native playback, keyframe bounding boxes, decisions and PDF access remain.
- Login uses SVG towers/cables, 10-second pulses and bounded pointer parallax.
  Night mode has a small moon/faint stars; daylight has restrained clouds and
  contrastive blue/cyan accents. Reduced motion stops movement; mobile prioritizes
  the form. No animation library is required.

## Demo assistant boundary

Dashboard and Metrics share `AssistantDock`. Inspection review has Findings and
Assistant tabs; video stays visible and draft state survives tab switching.
`AssistantPanel` handles multiline input, Enter/Shift+Enter, cancellation, retry,
conversation clearing, keyboard navigation and contextual timestamps.

`frontend/lib/assistant/types.ts::AssistantService` is the future transport boundary.
The separate local `mockAssistant` responds after a short delay with predefined text.
Conversations remain in React state, without localStorage, external AI requests,
database writes or new Backend endpoints. UI/replies explicitly say Demo and never
assert video analysis, new detections or verified metric conclusions. JSX renders
messages as text, without HTML execution. Real AI integration, editable profile
and power-line sections remain future work; sections are not video inspections.

## Checks

From `frontend/`, with dependencies installed:

```sh
npm test
npm run typecheck
npm run build
```

From the repository root, with Backend requirements installed, set `PYTHONPATH`
to `backend` and run:

```sh
python -m unittest discover -s backend/tests -p test_dashboard_kpis.py -v
```

For example, use `PYTHONPATH=backend python ...` on POSIX or
`$env:PYTHONPATH='backend'` in PowerShell. Tests use isolated SQLite/temporary
directories, never the live PostgreSQL database. The existing full pytest suite
additionally needs `backend/requirements-dev.txt`.

Manually verify themes/mobile, login/logout, upload/processing, exact seek and
marker/card synchronization, keyframe keyboard behavior, decisions and PDF.
Use isolated records for write tests; preserve shared engineer decisions.

See [design tokens](../frontend/DESIGN_SYSTEM.md),
[KPI rules](../frontend/DASHBOARD_KPI_API_REQUIREMENTS.md) and
[Docker instructions](../DOCKER_OPERATIONS.md).
