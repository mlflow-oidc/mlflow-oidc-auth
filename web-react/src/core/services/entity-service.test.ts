import { describe, it, expect, vi, type Mock } from "vitest";
import * as entityService from "./entity-service";
import * as apiUtils from "./api-utils";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

vi.mock("./api-utils", () => ({
  request: vi.fn(),
}));

describe("entity-service", () => {
  it("exported functions are defined", () => {
    expect(entityService.fetchAllGroups).toBeDefined();
    expect(entityService.fetchAllExperiments).toBeDefined();
    expect(entityService.fetchAllModels).toBeDefined();
    expect(entityService.fetchAllPrompts).toBeDefined();
  });

  it("all permission fetchers are defined", () => {
    expect(entityService.fetchExperimentUserPermissions).toBeDefined();
    expect(entityService.fetchUserExperimentPermissions).toBeDefined();
    expect(entityService.fetchGroupExperimentPermissions).toBeDefined();
  });

  it("fetchAllGroupDetails is defined", () => {
    expect(entityService.fetchAllGroupDetails).toBeDefined();
  });

  it("fetchAllGroupDetails requests the groups/details endpoint", async () => {
    (apiUtils.request as Mock).mockResolvedValue([]);

    await entityService.fetchAllGroupDetails();

    expect(apiUtils.request).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.GROUPS_DETAILS,
      expect.objectContaining({ method: "GET" }),
    );
  });
});
