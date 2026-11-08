# LineSight AI Frontend foundations

Implemented 2026-11-06. Primary reference: the supplied Linear screenshot and [Linear's interface refresh](https://linear.app/now/behind-the-latest-design-refresh). [Frame.io](https://frame.io/features/review-and-approval) informs precise video review; [Sentry](https://sentry.io/changelog/new-issue-details-ui-now-available/) informs separation of findings and workflow actions; [Grafana](https://grafana.com/docs/grafana/latest/visualizations/dashboards/) informs data-focused panels. No previous Figma designs were used for this pass.

## Foundations

### Workspace refinement specification — 2026-11-06

This pass follows the supplied Linear screenshot: a quiet expanded navigation, page-level dividers, a main working list and a secondary properties/analytics rail. The approved execution request authorizes implementing these refinements in place.

- Primary UI font: the locally installed **Proxima Nova Regular**, through CSS family alias `LineSight Proxima Nova`. Exact local source names: `Proxima Nova Regular` and `ProximaNova-Regular`. No desktop font is copied, downloaded or redistributed. The existing licensed Onest is the fallback for unavailable local faces and missing glyphs.
- Typography tokens: page `30/36` px at every viewport, section `20/28`, body/table `16/23`, controls `15/22` (16 px inputs where already specified), labels/sidebar `15/22`, metadata `14/20`, KPI readouts `26/32`. Enable kerning and ligatures; numeric data uses tabular lining figures. No visible utility text below 14 px.
- Keep the existing accessible neutral palettes. A page-level `workspace-section` uses a single divider instead of nested card borders. The Dashboard `summary-strip` has exactly three readouts with subtle separators; unavailable values are neutral em dashes with a short visible label and an accessible explanation.
- Dashboard: header → summary strip → recent inspection rows as the primary content. A secondary analytics rail contains the upload trend and the unavailable review distribution. At narrower widths, charts follow the list. Demo/roadmap links remain a subdued footer.
- Navigation is 208 px expanded, with a 68 px persisted icon mode. First visits at 1024–1279 px start compact; a saved choice always wins. Header height is 56 px with 44 px controls. Main content uses 20 px desktop and 16 px mobile gutters.
- Inspection: 900 px available workspace width enables a minimum 560 px video and a 320 px findings panel. Below that, stack the panels and constrain video height to the viewport. Keep one page scrollbar; remove the permanent scroll box around findings. Metadata is a compact disclosure, and key frames remain available within each finding's evidence disclosure.
- Timeline: retain 44 px hit areas, icon/color semantics, exact timestamps, clustering and keyboard selection. Remove repeated instructional copy from successful states; retain explicit loading/error/empty and invalid-time messages.
- Bound stalled JSON requests to 30 seconds so existing error/retry states can recover. Preserve all endpoints and payloads. Review aggregation remains unavailable until the Backend supports it.

- Local Proxima Nova Regular is primary. The installed face contains the complete Russian alphabet, but lacks Ә ә Ғ ғ Қ қ Ң ң Ө ө Ұ ұ Ү ү Һ һ. Onest's existing OFL-licensed variable file covers these characters and remains bundled as fallback. Browser glyph advances confirm Proxima for Latin/Russian and Onest for missing Kazakh letters; see `UI_DELIVERY.md`. No font CDN or unauthorized webfont is used.
- Body/tables: 16/23 px; controls/sidebar/labels: 15/22 px; metadata: 14/20 px; section headings: 20/28 px; page titles: 30/36 px; summary numbers: 26/32 px. CSS typography variables back Tailwind tokens. Preserve sentence case, moderate weights, kerning and tabular numeric data.
- Dark default: canvas `#101012`, panel `#151518`, raised surface `#1e1e22`, text `#eeeef2`, secondary text `#a7a7b4`, accent `#aab8ef`.
- Light: canvas `#f7f7f9`, panel white, raised surface `#efeff3`, text `#202027`, secondary text `#60606f`, accent `#41508a`.
- Semantic priorities: high red, medium amber, low blue, insufficient visibility gray plus a crossed-eye icon. Confirmation uses green only after an engineer's decision. Video processing completion is neutral and says “Обработано”.
- Spacing follows a 4 px base, with 12/16/20/24 px composition gaps. Panels use thin borders and 6–8 px primary corner radii; shadows are reserved for overlays. No gradients or glow.
- Shared CSS component classes: `panel`, `btn`, `btn-primary`, `icon-button`, `page-title`. Colors remain reusable Tailwind tokens backed by CSS channel variables; SVG aliases share the same palette.

## Interaction

- `ls_theme`: explicit saved choice wins; no saved choice means dark. A synchronous head script applies it before content paints. Storage events synchronize open tabs; blocked storage still permits session switching.
- Sidebar: 208 px expanded, 68 px collapsed, preference `ls_sidebar_collapsed`. An existing explicit saved choice is respected. Both navigation variants scroll when the viewport is too short. Mobile navigation remains in normal flow, moves focus into links and supports Escape with focus restoration. All working routes remain available; demo pages are secondary navigation.
- Findings panel is independent of the sidebar. Container widths of 900/1120/1380 px enable 320/352/384 px panels, separated by 20 px. The review page is capped at 1480 px. At narrower widths the panels stack, with two finding columns only at 650–899 px. The video column is sticky only at viewport heights of at least 760 px; video height leaves room for native controls and the compact timeline. There is no permanent nested findings scrollbar. Cards use one action row when their own content width reaches 326 px; otherwise confirmation spans the first row.
- Timeline clusters findings whose anchors would be less than 44 px apart. A group is anchored at its first timestamp and exposes its time range; every member retains its exact API timestamp. Choosing a member seeks exactly and highlights its card/group. Invalid timestamps remain in the finding list with an explicit warning.
- On stacked mobile layouts, marker selection keeps the video/group chooser in view. Card selection reveals the video. Scripted scrolling respects reduced motion; CSS removes motion when requested.
- Primary touch controls and marker hit areas are at least 44 px. Focus rings, keyboard controls, visible errors/retries, accessible group tooltips and dialog focus restoration are required patterns.

## Data boundaries

The Dashboard has exactly three primary KPIs: Total Inspections, Detected Defects and Confirmed Defects. All three use authoritative `/api/metrics` aggregates; an older API without the defect fields remains explicitly unavailable. Total findings include capture-quality/equipment observations and cannot substitute for defect totals. Confirmed defects require both semantic defect classification and an explicit engineer decision. See `DASHBOARD_KPI_API_REQUIREMENTS.md` for the implemented additive contract. Finding review distribution remains unavailable until a dedicated aggregate is provided. Inspection trends count actual uploads by `created_at`; they never imply processing completion. Do not fetch every inspection's findings to synthesize aggregates.

Technical metrics remain separate. Power-line sections are infrastructure entities; inspections are video records. Sections, editable profile and real AI integration remain roadmap features. The contextual assistant UI uses a labeled local mock service and does not analyze videos, verify metrics or change decisions. Existing demos are never mixed into real statistics.

The readout strip and neutral unavailable indicators replace the previous four-card Dashboard. Recent inspections are the main workspace; two analytics sections occupy a secondary rail only when sufficient content width is available. On phones, each semantic table row presents title/status and date/finding count without requiring horizontal scrolling.

## Information density

- Dashboard: exactly three readouts; 20 px section gaps; a 280 px analytics rail when the content container reaches 1000 px. Search/status controls are shared with the inspections list. Table links retain 44 px targets and rows are approximately 48 px high for single-line titles. Real zero values remain distinct from missing aggregates.
- Inspections: the table is the primary workspace. The New Inspection disclosure opens for `#new-inspection`; its form stays mounted when collapsed, preserving file selection, text and upload progress.
- Metrics: a 1440 px page cap and explicit table column proportions align stage values. Horizontal scrolling belongs to the table on narrow screens; numeric and body text stays 16 px.
- Evidence: a keyframe dialog has a fixed header and one scrollable image region. Bounding boxes remain percentage-based inside the image wrapper. Escape, Tab/Shift+Tab, body scroll restoration and focus return are preserved.
