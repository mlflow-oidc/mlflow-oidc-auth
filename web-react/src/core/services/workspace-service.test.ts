import { describe, it, expect } from "vitest";
import {
  fetchAllWorkspaces,
  fetchWorkspaceUsers,
  fetchWorkspaceGroups,
} from "./workspace-service";

describe("workspace-service", () => {
  it("exports fetchAllWorkspaces as a function", () => {
    expect(typeof fetchAllWorkspaces).toBe("function");
  });

  it("exports fetchWorkspaceUsers as a function", () => {
    expect(typeof fetchWorkspaceUsers).toBe("function");
  });

  it("exports fetchWorkspaceGroups as a function", () => {
    expect(typeof fetchWorkspaceGroups).toBe("function");
  });
});
