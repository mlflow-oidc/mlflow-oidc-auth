import { describe, it, expect } from "vitest";
import { getSidebarData } from "./sidebar-data";

describe("sidebar-data", () => {
  it("returns base links for non-admin", () => {
    const data = getSidebarData(false, false, false);
    // Users, Service Accounts, Groups, Experiments, Prompts, Models, MCP Servers, Skills = 8
    expect(data).toHaveLength(8);
    expect(data.map((item) => item.label)).toContain("MCP Servers");
    expect(data.map((item) => item.label)).toContain("Skills");
    expect(data.map((item) => item.label)).not.toContain("Trash");
    expect(data.map((item) => item.label)).not.toContain("Detection schedules");
  });

  it("returns extra links for admin", () => {
    const data = getSidebarData(true, false, false);
    // 8 base + Trash + Webhooks + SCIM + Detection schedules = 12
    expect(data).toHaveLength(12);
    expect(data.map((item) => item.label)).toContain("Trash");
    expect(data.map((item) => item.label)).toContain("Webhooks");
    expect(data.map((item) => item.label)).toContain("SCIM");
    expect(data.map((item) => item.label)).toContain("Detection schedules");
  });

  it("returns AI Gateway links when enabled", () => {
    const data = getSidebarData(false, true, false);
    // 8 base + 3 AI = 11
    expect(data).toHaveLength(11);
    expect(data.map((item) => item.label)).toContain("AI Endpoints");
    expect(data.map((item) => item.label)).toContain("AI Secrets");
    expect(data.map((item) => item.label)).toContain("AI Models");
  });

  it("returns Workspaces link when workspaces enabled", () => {
    const data = getSidebarData(false, false, true);
    // 8 base + 1 workspace = 9
    expect(data).toHaveLength(9);
    expect(data.map((item) => item.label)).toContain("Workspaces");
  });

  it("returns all links when everything enabled", () => {
    const data = getSidebarData(true, true, true);
    // 8 base + 3 AI + 1 workspace + 4 admin + Workspace rules = 17
    expect(data).toHaveLength(17);
    expect(data.map((item) => item.label)).toContain("AI Endpoints");
    expect(data.map((item) => item.label)).toContain("Workspaces");
    expect(data.map((item) => item.label)).toContain("Trash");
    expect(data.map((item) => item.label)).toContain("Webhooks");
    expect(data.map((item) => item.label)).toContain("SCIM");
    expect(data.map((item) => item.label)).toContain("Workspace rules");
  });
});
