import { describe, it, expect, vi } from "vitest";
import { cleanupTrash, restoreExperiment } from "./trash-service";
import { http } from "./http";
import { getRuntimeConfig } from "../../shared/services/runtime-config";

vi.mock("./http");
vi.mock("../../shared/services/runtime-config", () => ({
  getRuntimeConfig: vi.fn(() =>
    Promise.resolve({
      basePath: "",
      uiPath: "",
      provider: "",
      authenticated: true,
    }),
  ),
}));

describe("trash-service", () => {
  it("cleanupTrash calls http with correct params", async () => {
    await cleanupTrash({ older_than: "7d" });
    expect(http).toHaveBeenCalledWith(
      expect.stringContaining("older_than=7d"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("restoreExperiment calls correct endpoint", async () => {
    await restoreExperiment("123");
    expect(http).toHaveBeenCalled();
  });

  it("prefixes URL with basePath from runtime config", async () => {
    vi.mocked(getRuntimeConfig).mockResolvedValue({
      basePath: "/mlflow",
      uiPath: "",
      provider: "",
      authenticated: true,
    });
    await cleanupTrash({ older_than: "7d" });
    expect(http).toHaveBeenCalledWith(
      expect.stringMatching(/^\/mlflow\/oidc\/trash\/cleanup\?older_than=7d$/),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
