# Existing application flow

1. `/login`: existing login/password API creates the session. Invalid input/server errors remain visible and the form permits retry. Logout ends the session and returns here.
2. `/` redirects to `/dashboard`. Protected application pages retain the existing authentication behavior.
3. `/dashboard`: three primary summary values (total inspections, detected defects, engineer-confirmed defects), search/status filtering and pagination of real inspections. Defect aggregates remain explicitly unavailable until supported by the Backend. The main title link in a row opens that inspection. “Новая инспекция” navigates to `/inspections#new-inspection`.
4. `/inspections`: upload an MP4 (existing limit 500 MB), name it and follow real upload progress. A successful upload opens `/inspections/[id]`; list polling retains processing statuses and explicit error/retry states.
5. `/inspections/[id]`: queued/processing/failed/completed states remain distinct. Native playback and synchronized timeline expose real findings. A marker or finding seeks to its exact timestamp; a grouped marker exposes each member. Marker selection opens the findings panel and resets a filter if needed to show the selected item.
6. The findings status selector includes all/new/confirmed/rejected/reshoot and their local counts. Key-frame disclosures preserve frame viewing, bbox and zoom. Confirm/reject/reshoot preserve the existing PATCH contract and per-finding retry behavior. Real PDF download remains available for completed inspections and is disabled while decisions are pending.
7. `/metrics`: average processing time, FPS, failure share and per-run stage timings; row titles open their inspection. This page remains separate from the operational Dashboard.
8. `/sections` and `/preview`: existing, explicitly labeled demos. They do not create or alter real inspection data. Sections, profile editing and contextual assistance remain roadmap features.

Dark is the default theme; saved light/dark and sidebar preferences persist. Desktop navigation is expanded unless the user explicitly saved its collapsed state. Mobile navigation supports Escape/focus restoration. The findings-panel toggle is independent of navigation state. All routes remain accessible.
