# Frontend boundaries

Preserve the existing Next.js App Router application. Architecture patterns are applied to the small boundaries that already exist; do not introduce a Backend rewrite or a hierarchy of unnecessary service classes.

- `lib/types.ts` describes the existing transport contracts. Keep it free of React and invented Backend fields.
- `lib/api.ts` is the authenticated HTTP adapter. It owns existing paths, payloads, session headers/cookies, PDF transport and bounded request lifetimes. JSON requests have a 30-second deadline including response-body reading; PDF downloads have 90 seconds. MP4 upload keeps its existing XHR progress contract.
- `lib/dashboard.ts` is a framework-free presentation boundary. It filters, orders and derives upload trends from the real inspection list. `dashboardSummary` distinguishes unavailable finding aggregates (`null`) from a valid total of zero. No React, network requests or per-inspection fetching belongs here.
- `lib/review.ts` applies per-finding results and guarded rollback. A failed decision cannot restore the whole array or overwrite a different finding/newer decision. Keep it unit-testable without a browser, database or Docker.
- Hooks orchestrate resource state. Preserve serial polling, stale-result guards, last-good data and explicit retry controls. UI components own transient selection, disclosures and layout state.
- Shared typography, spacing, semantic palette and workspace layout tokens live in `app/globals.css` and `tailwind.config.ts`. Use `page-title`, `section-title`, `summary-strip`, `workspace-section`, `btn` and `icon-button` consistently. The local Proxima Nova source uses its exact installed names and falls back to Onest; do not copy the installed desktop font into web assets. Page/section/body-table/control-label/metadata sizes are 30/20/16/15/14 px. No visible metadata below 14 px.
- Native video controls remain available. Exact API timestamps pass through the timeline into `VideoPlayer` without rounding. Grouping changes presentation, not finding timecodes.
- Evidence and metadata use native disclosures; zoom dialogs retain Escape, focus containment/restoration and backdrop-only dismissal. Respect reduced motion for scripted as well as CSS scrolling.

## Future boundaries

Power-line sections are infrastructure entities. Inspections are individual uploaded video records. Keep demo section data separate until a real catalog and association contract exist; do not add imaginary `section_id` fields or endpoints.

Editable profile needs an actual identity/update contract before it can become a working route. A contextual assistant should consume a defined finding/review context through an adapter and clearly distinguish rules, model suggestions and engineer decisions. Neither future feature is presented as functional today.

Tests for filtering, availability, review concurrency, exact timing and transport run without a Backend. Visual QA uses a synchronized temporary Frontend copy outside the Docker build context and the existing real Backend. Never modify the reference project or real review decisions merely to validate styling.
