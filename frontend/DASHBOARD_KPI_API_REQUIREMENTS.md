# Dashboard KPI contract

Authenticated `GET /api/metrics` retains its technical fields and adds three
nonnegative integer aggregates from persisted database rows:

| Field | Counting rule |
| --- | --- |
| `inspections_total` | All persisted inspections, including queued, processing, done and failed. |
| `detected_defects_total` | Current persisted equipment-defect findings, across all review statuses. |
| `confirmed_defects_total` | The same eligible subset with current status exactly `confirmed`. |

Confirmed is a subset of detected. The engineer decision API writes review status;
rejection/reshoot changes confirmed without deleting the persisted detection.
These counters are not a cumulative audit of deleted findings.

`backend/app/defect_policy.py` uses persisted identifiers and the existing
`ml/classes.py` taxonomy. Equipment-damage dataset codes qualify. `nw` (nest),
`yw` (foreign object), `low_visibility`, generic equipment, technical errors and
unknown observations do not. Recognized equipment plus a damage keyword supports
existing textual damage classes. New vocabularies need explicit policy review.
Priority alone is not eligibility: a low-confidence damage candidate still counts,
while confirmed visibility remains capture quality.

`backend/app/repository.py::metrics` groups findings by type with row counts and
conditional confirmed counts. It neither loads finding objects nor joins them
into inspection totals. Existing unique track/type persistence prevents repeated
worker saves from creating duplicates. No migration or new endpoint is required.

The endpoint and frontend aggregate/list reads use `no-store`. Dashboard refreshes
on mount, focus, visibility restoration and successful upload/review events. It
polls every 5 seconds during processing/recovery and every 30 seconds when idle,
coalesces requests and pauses while hidden. No per-inspection API loop is used.

Zero is a successful aggregate. Initial failures and missing fields from an older
Backend remain unavailable; partial failures keep last-good data with retry feedback.
Inspection-list length and total finding counts are never substitutes.
Review-status distribution still requires its own Backend aggregate.

Tests: `backend/tests/test_dashboard_kpis.py`, `frontend/lib/dashboard.test.ts`,
`frontend/lib/dashboardPolling.test.ts`, `frontend/lib/api.test.ts`.
