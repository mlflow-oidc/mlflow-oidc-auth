/** Shortest and longest lifetime, in whole UTC calendar days from today, a new token may have. */
export const MIN_TOKEN_DAYS = 1;
export const MAX_TOKEN_DAYS = 365;
/** Preselected lifetime for a new token. */
export const DEFAULT_TOKEN_DAYS = 90;

const pad = (value: number): string => String(value).padStart(2, "0");

/**
 * The UTC calendar date `days` after `now`, as `YYYY-MM-DD`.
 *
 * The picker works in UTC calendar days because the expiration it produces is the end of that
 * UTC day. Using the viewer's local "today" instead would let someone east of UTC pick a day
 * whose end lies past the backend's one-year cap.
 */
export function utcDateAfter(now: Date, days: number): string {
  const date = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + days),
  );
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

/** The `min`/`max`/default values for the expiration date picker. */
export function tokenDateBounds(now: Date = new Date()): {
  min: string;
  max: string;
  defaultValue: string;
} {
  return {
    min: utcDateAfter(now, MIN_TOKEN_DAYS),
    max: utcDateAfter(now, MAX_TOKEN_DAYS),
    defaultValue: utcDateAfter(now, DEFAULT_TOKEN_DAYS),
  };
}

const DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/**
 * The end of the picked calendar day in UTC, e.g. `2027-01-31` becomes `2027-01-31T23:59:59Z`.
 *
 * Built from the date parts, never through `new Date(...)`, so the viewer's timezone cannot
 * shift the day.
 *
 * @returns The ISO timestamp, or null when `date` is not a real `YYYY-MM-DD` date.
 */
export function endOfUtcDayIso(date: string): string | null {
  const match = DATE_PATTERN.exec(date);
  if (!match) return null;
  const [, year, month, day] = match;
  const check = new Date(
    Date.UTC(Number(year), Number(month) - 1, Number(day)),
  );
  if (
    check.getUTCFullYear() !== Number(year) ||
    check.getUTCMonth() !== Number(month) - 1 ||
    check.getUTCDate() !== Number(day)
  ) {
    return null;
  }
  return `${year}-${month}-${day}T23:59:59Z`;
}

/** Whether `date` lies within picker bounds (lexicographic order is date order here). */
export function isWithinTokenDateBounds(
  date: string,
  bounds: { min: string; max: string },
): boolean {
  return date >= bounds.min && date <= bounds.max;
}
