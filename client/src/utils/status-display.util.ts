/**
 * Shared status-display helpers used by the dashboard and status pages.
 *
 * Kept in one place so backend status renames need exactly one update.
 */

const IN_PROGRESS = new Set(['Pending', 'Cloned', 'Cached', 'Testing', 'Evaluating']);
const ERROR = new Set(['Failed', 'EVALUATION_FAILED']);

const BADGE_TONE: Record<string, string> = {
  'In Progress': 'blue',
  'Awaiting Review': 'amber',
  Completed: 'green',
  Rejected: 'red',
  Error: 'red',
};

export function displayStatus(rawStatus: string): string {
  if (IN_PROGRESS.has(rawStatus)) return 'In Progress';
  if (ERROR.has(rawStatus)) return 'Error';
  return rawStatus;
}

export function badgeTone(displayedStatus: string): string {
  return BADGE_TONE[displayedStatus] ?? 'neutral';
}
