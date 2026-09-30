import { describe, it, expect } from "vitest";
import { buildRulePattern, escapeRegex } from "./rule-builder";

describe("buildRulePattern", () => {
  it("maps one group to its workspace", () => {
    expect(buildRulePattern("team-acme-ds", "acme", false)).toEqual({
      ok: true,
      pattern: "^team-(?P<ws>acme)-ds$",
      name: "team-acme-ds → acme",
    });
  });

  it("covers every group of the same shape", () => {
    expect(buildRulePattern("team-acme-ds", "acme", true)).toEqual({
      ok: true,
      pattern: "^team-(?P<ws>[a-z0-9-]+)-ds$",
      name: "team-*-ds",
    });
  });

  it("escapes the literal parts, including a provider prefix", () => {
    const built = buildRulePattern("partner:team.acme+x", "acme", false);
    expect(built).toEqual(
      expect.objectContaining({ pattern: "^partner:team\\.(?P<ws>acme)\\+x$" }),
    );
  });

  it("matches the examples in docs/admin-ui.md", () => {
    const pattern = (group: string, workspace: string, every: boolean) => {
      const built = buildRulePattern(group, workspace, every);
      return built.ok ? built.pattern : null;
    };
    expect(pattern("partner:ml-acme", "acme", true)).toBe(
      "^partner:ml-(?P<ws>[a-z0-9-]+)$",
    );
    expect(pattern("acme", "acme", false)).toBe("^(?P<ws>acme)$");
  });

  it("prefers an occurrence delimited by separators", () => {
    const built = buildRulePattern("teamacme-acme", "acme", false);
    expect(built).toEqual(
      expect.objectContaining({ pattern: "^teamacme-(?P<ws>acme)$" }),
    );
  });

  it("refuses a group whose name does not contain the workspace", () => {
    const built = buildRulePattern("data-scientists", "acme", false);
    expect(built.ok).toBe(false);
    expect(!built.ok && built.reason).toContain(
      "Grant this group on the workspace's page",
    );
  });

  it("escapes every character Python's re treats specially", () => {
    expect(escapeRegex("a.b*c+d?e^f$g{h}i(j)k|l[m]n\\o")).toBe(
      "a\\.b\\*c\\+d\\?e\\^f\\$g\\{h\\}i\\(j\\)k\\|l\\[m\\]n\\\\o",
    );
  });
});
