import { describe, it, expect } from "vitest";
import * as mcpServerService from "./mcp-server-service";

describe("mcp-server-service", () => {
  it.each([
    "fetchAllMcpServers",
    "fetchMcpServersPage",
    "fetchMcpServerUserPermissions",
    "fetchMcpServerGroupPermissions",
    "fetchUserMcpServerPermissions",
    "fetchGroupMcpServerPermissions",
  ] as const)("%s is a function", (name) => {
    expect(typeof mcpServerService[name]).toBe("function");
  });

  it("exposes no pattern fetchers: MCP servers have no pattern API", () => {
    expect(
      Object.keys(mcpServerService).filter((k) => k.includes("Pattern")),
    ).toEqual([]);
  });
});
