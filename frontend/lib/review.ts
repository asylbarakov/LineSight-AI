import type { Decision, Finding } from "./types";

export function replaceFinding(rows: Finding[], saved: Finding): Finding[] {
  return rows.map(row => row.id === saved.id ? saved : row);
}

/** A failed request must never roll back other findings or a newer decision. */
export function rollbackFinding(rows: Finding[], previous: Finding, attempted: Decision): Finding[] {
  return rows.map(row => row.id === previous.id && row.status === attempted ? previous : row);
}
