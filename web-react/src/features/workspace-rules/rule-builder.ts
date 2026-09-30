/**
 * Build a workspace rule pattern from an example: an existing group and the workspace it should
 * get. A rule's `(?P<ws>…)` group captures the workspace name from inside the group name, so this
 * works only when the group's name contains the workspace's name — `team-acme-ds` and `acme`.
 */

/** The characters Python's `re` treats specially outside a character class. */
const REGEX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

/** Escape `text` so a Python regular expression matches it literally. */
export function escapeRegex(text: string): string {
  return text.replace(REGEX_SPECIAL, "\\$&");
}

/** What the workspace part matches when a pattern covers every group of the same shape. */
export const ANY_WORKSPACE = "[a-z0-9-]+";

export type BuiltRulePattern =
  | { ok: true; pattern: string; name: string }
  | { ok: false; reason: string };

const WORD_CHAR = /[a-z0-9]/i;

/**
 * Where `workspace` appears in `group`. An occurrence delimited by the ends of the name or by a
 * separator (`team-acme-ds`) is preferred over one inside a longer word (`teamacme`).
 */
function findWorkspace(group: string, workspace: string): number {
  let fallback = -1;
  for (
    let at = group.indexOf(workspace);
    at !== -1;
    at = group.indexOf(workspace, at + 1)
  ) {
    const before = at === 0 ? "" : group[at - 1];
    const after = group[at + workspace.length] ?? "";
    if (!WORD_CHAR.test(before) && !WORD_CHAR.test(after)) return at;
    if (fallback === -1) fallback = at;
  }
  return fallback;
}

/**
 * The rule pattern mapping `group` to `workspace`.
 *
 * @param group - An existing local group name, e.g. `team-acme-ds` or `partner:team-acme-ds`.
 * @param workspace - An existing workspace name, e.g. `acme`.
 * @param everyLikeGroup - Match every group with the same prefix and suffix
 *   (`^team-(?P<ws>[a-z0-9-]+)-ds$`) instead of this group alone (`^team-(?P<ws>acme)-ds$`).
 */
export function buildRulePattern(
  group: string,
  workspace: string,
  everyLikeGroup: boolean,
): BuiltRulePattern {
  if (!group || !workspace) {
    return { ok: false, reason: "Choose a group and a workspace." };
  }
  const at = findWorkspace(group, workspace);
  if (at === -1) {
    return {
      ok: false,
      reason: `The group name does not contain the workspace name "${workspace}", so a rule cannot derive the workspace from it. Grant this group on the workspace's page instead.`,
    };
  }
  const prefix = group.slice(0, at);
  const suffix = group.slice(at + workspace.length);
  const captured = everyLikeGroup ? ANY_WORKSPACE : escapeRegex(workspace);
  const pattern = `^${escapeRegex(prefix)}(?P<ws>${captured})${escapeRegex(suffix)}$`;
  const name = everyLikeGroup
    ? `${prefix}*${suffix}`
    : `${group} → ${workspace}`;
  // Rule names are at most 255 characters.
  return { ok: true, pattern, name: name.slice(0, 255) };
}
