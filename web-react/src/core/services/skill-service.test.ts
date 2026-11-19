import { describe, it, expect } from "vitest";
import * as skillService from "./skill-service";

describe("skill-service", () => {
  it.each([
    "fetchAllSkills",
    "fetchSkillsPage",
    "fetchSkillUserPermissions",
    "fetchSkillGroupPermissions",
    "fetchUserSkillPermissions",
    "fetchGroupSkillPermissions",
  ] as const)("%s is a function", (name) => {
    expect(typeof skillService[name]).toBe("function");
  });

  it("exposes no pattern fetchers: skills have no pattern API", () => {
    expect(
      Object.keys(skillService).filter((k) => k.includes("Pattern")),
    ).toEqual([]);
  });
});
