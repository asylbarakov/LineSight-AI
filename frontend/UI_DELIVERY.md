# Frontend UI delivery

This feature branch continues the working Next.js application from remote `asyl_experiment` at `f6dc9fec8e94ccc0e9aed702492f078a7b40797c`. Its existing Backend/ML/API/Docker configuration is preserved. It is not a port or merge into `main`.

## History and scope

Before transfer, all 55 inspected Backend/ML/Docker/configuration files in the working extraction matched their Git blobs on `asyl_experiment`. The 35 inspected reference-project files matched `feat/backend-worker`. The remote `main` branch has a different Backend/API structure; integration with it requires a separate compatibility review and is outside this isolated delivery. No existing remote branch is a push target.

Only reviewed Frontend source, tests, design/flow/API requirements documentation and the licensed Onest fallback were transferred. The package manifest, transport types, Backend, ML, Dockerfile and Next.js upload/proxy configuration retain the base contract. No files are deleted from the base. Teammates' files outside this Frontend scope are preserved.

The diff review also retained the base inspection page's detailed processing-error paragraph (`error_message`) alongside the redesigned error state. Transfer-only cleanup removes excess trailing whitespace/blank lines and makes the design documentation portable; the original extraction is unchanged.

## Included behavior

- Exactly three Dashboard KPIs: Total Inspections, Detected Defects, Confirmed Defects. Real inspection totals; defect aggregates remain explicitly unavailable until supported by the Backend. No N+1 findings aggregation or fabricated statistics. See `DASHBOARD_KPI_API_REQUIREMENTS.md`.
- Real inspection list/search/status filters, actual upload trends, explicit unavailable finding-review distribution and a separate technical Metrics page.
- Near-black default and persisted light/dark themes, shared tokens, expanded/collapsible persisted navigation and accessible mobile menu.
- Video-first inspection workspace, independent findings panel, exact timestamp icon markers and overlap groups, synchronized finding selection, per-finding guarded review rollback, evidence dialogs and existing PDF downloads.
- Existing MP4 upload, processing states and authentication API contracts remain intact. JSON requests retain a bounded 30-second lifetime; PDF requests use 90 seconds.
- Login-only two-column line-scan illustration: lightweight SVG and synchronized 10-second CSS animation with pause/resume. Static reduced-motion presentation; simplified tablet view and illustration hidden on phones. Original validation, authentication and redirect behavior remain unchanged.
- Sections and preview remain clearly labeled demonstrations. Editable profile and contextual assistance remain roadmap items; no invented API endpoints.

## Font rights and rendering

Proxima Nova uses CSS `local("Proxima Nova Regular")` / `local("ProximaNova-Regular")` through the `LineSight Proxima Nova` alias. No proprietary Proxima font binary is included. Clients without the installed face use the bundled Onest, then system fallbacks. Native Proxima semibold/bold webfonts were not supplied.

The existing Windows browser verification matched the installed Proxima metrics for Latin/Russian: ten H/Н glyphs at 32 px measured 227.85 px, versus Onest's 232.65 px. The 16 missing Kazakh characters ӘәҒғҚқҢңӨөҰұҮүҺһ used the Onest fallback. These are environment-specific rendering observations, not a claim that Proxima is installed on every client. The distributable Onest font is accompanied by `public/fonts/OFL-Onest.txt` (SIL OFL 1.1).

## Validation and development

Existing checks from `frontend/`:

```text
npm test
npm run typecheck
npm run build
```

The transfer is checked in this Git-backed copy using existing dependencies, with no package/lockfile changes or Docker containers. Prior visual verification against the existing Backend covered both themes, desktop/tablet/mobile layouts, real login/logout, credential errors, native video playback, exact marker/card seeks and PDF access. The reduced-motion CSS rules were inspected; the Windows preference itself was not toggled. Generated screenshots/PDFs and machine-specific deployment reports are intentionally excluded.

Fresh transfer checks passed: 65 tests in seven files, TypeScript, optimized Next.js 15.5.29 standalone build and staged whitespace checks. The staged inventory contains 58 Frontend files, including five Markdown documents and the OFL-licensed fallback font. A path/content check found no excluded payloads, common token/private-key literals or the inspected local secret values. The 72 reviewed source files in the original extraction remained unchanged.

The clone uses sparse checkout for `.github`, `backend`, `docs`, `frontend`, `ml` and `scripts`, plus root files. Existing tracked media/weights remain in the base history but are not checked out or added by this UI commit. The original extracted working and reference directories are retained. Existing running Docker services/data are not controlled by this new checkout during this task; deployment is separate.

Local `.env*`, credentials, databases, media, weights, build output, dependency directories and validation artifacts are not part of this Frontend change. The Frontend ignore file also excludes local environment files, artifacts, coverage and logs.
