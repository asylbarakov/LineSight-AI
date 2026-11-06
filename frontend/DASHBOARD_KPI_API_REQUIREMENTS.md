# Dashboard KPI data requirements

2026-11-06. Frontend-only change; the Backend proposal below is not implemented.

## Current UI

Exactly three primary readouts are shown: Total Inspections (Всего инспекций), Detected Defects (Обнаружено дефектов), Confirmed Defects (Подтверждено дефектов).

Total uses the real `GET /api/metrics.inspections_total`, with the current complete inspection list as fallback. Zero remains zero. Both defect totals show an em dash and “Нет сводки”, with accessible explanations. Neither is inferred from inspection counts, processing status, priority, or total findings. No per-inspection requests were added. Charts, filters, pagination and inspection navigation retain their existing behavior.

## Inspected contracts and model

- `backend/app/main.py`: `/api/inspections` returns summaries whose `findings_count` includes every finding. `/api/inspections/{id}/findings` only covers one inspection. `/api/metrics` delegates to the repository; there is no global findings aggregate endpoint.
- `backend/app/repository.py`, `metrics`: returns inspection total, average processing time/FPS, failure share and recent runs, without defect totals. `set_finding_status` records an engineer decision and `decided_at`; findings are created as `new`, not automatically confirmed.
- `backend/app/db.py`, `Finding`: stores `type`, `priority`, `status` and nullable `decided_at`. A finding is a tracked type within an inspection, not one video frame or one inspection. There is no persisted semantic category or reviewer identity. The current finding response does not expose `decided_at`.
- `ml/classes.py`: broad problem classification includes damage classes, but also bird nests (`nw`), foreign objects (`yw`) and keyword hazards. Generic equipment detections are not equipment defects. Reusing this broad predicate unchanged would silently mix categories.
- `ml/scoring.py`: priority is independent of semantic kind. `low_visibility` is a capture-quality observation. `insufficient_data` can also describe low-confidence defect candidates; excluding every finding with that priority would incorrectly discard a defect an engineer later confirms. Low priority alone does not exclude defects either.
- `frontend/lib/types.ts` preserves the existing transport types. `frontend/components/dashboard/useDashboardData.ts` still requests only inspections and metrics per polling cycle; it does not fetch each inspection's findings.

## Minimal additive Backend proposal

Extend the existing authenticated `GET /api/metrics` response with two nullable nonnegative integer fields, preserving every current field and its meaning:

| Proposed field | Meaning |
| --- | --- |
| `defects_detected_total` | Distinct persisted findings classified as equipment-defect candidates by a canonical, explicitly maintained type mapping. These are model detections, not confirmed faults. |
| `defects_confirmed_total` | The same semantic defect subset, additionally requiring current `status == "confirmed"` and `decided_at IS NOT NULL`, written through the engineer decision flow. |

First define one authoritative category mapping: equipment defect, capture quality, equipment observation, hazard, unknown. Exclude `low_visibility`, generic equipment, unknown observations, nests and foreign objects from equipment-defect counts. If hazards are intended to be included, explicitly approve that product definition and communicate it in the labels; do not infer it from `is_defect`, priority or engineer status alone. Apply this mapping to the actual stored type vocabulary. Do not duplicate fuzzy classification in the Frontend.

Recommended detected-total policy: count current persisted model candidates across all review states, including rejected/reshoot, as detection history; only the confirmed total asserts engineer acceptance. This is not a cumulative audit of deleted/reprocessed findings. Agree and document the policy before supplying the new fields. If the product instead wants non-rejected candidates, define that explicitly rather than changing the number silently.

Compute both totals together server-side using conditional aggregation over distinct finding IDs, within the same authorization scope as the inspection total. Preserve the separate inspection count to avoid multiplying it in a one-to-many join. Use a constant number of database queries, never a per-inspection API loop. Existing type/status/decision-time columns are sufficient once the mapping is agreed; a database migration or exposing individual decision timestamps is not required for these aggregate fields. Durable semantic categories and reviewer audit identity can be considered separately.

Return `null` when an accurate aggregate cannot be supplied. Return `0` only after successful authoritative computation. The Frontend must keep unknown/missing fields unavailable and may consume these fields only after the real contract is implemented and verified. This change deliberately adds no speculative fields to Frontend types.

## Backend acceptance cases

- New defect candidate: detected, not confirmed.
- Confirmed equipment defect with a recorded decision: detected and confirmed, even if its original priority was `insufficient_data`.
- Rejected/reshoot defect: not confirmed; detected according to the explicitly agreed candidate policy.
- Confirmed `low_visibility`, generic equipment or non-defect observation: neither defect total.
- Nest/foreign-object hazard or unknown type: excluded from equipment defects under the proposed narrow mapping; insufficient taxonomy coverage makes aggregation unavailable rather than guessed.
- Empty, successfully classified dataset: both counts zero. Missing aggregate support: both unavailable.
- Multiple frames for one persisted tracked finding: count that finding once. No joins inflate the inspection total.

## Frontend validation

Regression coverage in `lib/dashboard.test.ts` verifies exactly three summary values, unavailable defect totals despite nonzero total finding counts, preservation of a real zero and precedence of the real inspection aggregate. Full Frontend checks and rendered-theme verification are recorded in `progress.txt`.
