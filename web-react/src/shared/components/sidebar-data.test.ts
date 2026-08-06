import { describe, it, expect } from "vitest";
import { getSidebarData } from "./sidebar-data";

describe("sidebar-data", () => {
  it("returns base links for non-admin", () => {
    const data = getSidebarData(false, false, false);
    // Users, Service Accounts, Groups, Experiments, Prompts, Models = 6
    expect(data).toHaveLength(6);
    expect(data.map((item) => item.label)).not.toContain("Trash");
  });

  it("returns extra links for admin", () => {
    const data = getSidebarData(true, false, false);
    // 6 base + Trash + Webhooks = 8
    expect(data).toHaveLength(8);
    expect(data.map((item) => item.label)).toContain("Trash");
    expect(data.map((item) => item.label)).toContain("Webhooks");
  });

  it("returns AI Gateway links when enabled", () => {
    const data = getSidebarData(false, true, false);
    // 6 base + 3 AI = 9
    expect(data).toHaveLength(9);
    expect(data.map((item) => item.label)).toContain("AI Endpoints");
    expect(data.map((item) => item.label)).toContain("AI Secrets");
    expect(data.map((item) => item.label)).toContain("AI Models");
  });

  it("returns Workspaces link when workspaces enabled", () => {
    const data = getSidebarData(false, false, true);
    // 6 base + 1 workspace = 7
    expect(data).toHaveLength(7);
    expect(data.map((item) => item.label)).toContain("Workspaces");
  });

  it("returns all links when everything enabled", () => {
    const data = getSidebarData(true, true, true);
    // 6 base + 3 AI + 1 workspace + 2 admin = 12
    expect(data).toHaveLength(12);
    expect(data.map((item) => item.label)).toContain("AI Endpoints");
    expect(data.map((item) => item.label)).toContain("Workspaces");
    expect(data.map((item) => item.label)).toContain("Trash");
    expect(data.map((item) => item.label)).toContain("Webhooks");
  });
});
