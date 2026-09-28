import { describe, it, expect, vi, type Mock } from "vitest";
import * as entityService from "./entity-service";
import * as apiUtils from "./api-utils";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";

vi.mock("./api-utils", () => ({
  request: vi.fn(),
  requestWithStatus: vi.fn(),
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

  it("createGroup posts the group name to the groups endpoint and surfaces the status", async () => {
    (apiUtils.requestWithStatus as Mock).mockResolvedValue({
      data: { message: "Group analysts successfully created" },
      status: 201,
    });

    const result = await entityService.createGroup("analysts");

    expect(apiUtils.requestWithStatus).toHaveBeenCalledWith(
      STATIC_API_ENDPOINTS.ALL_GROUPS,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ group_name: "analysts" }),
      }),
    );
    expect(result).toEqual({
      message: "Group analysts successfully created",
      status: 201,
    });
  });

  it("createGroup surfaces a 200 status when the group already existed", async () => {
    (apiUtils.requestWithStatus as Mock).mockResolvedValue({
      data: { message: "Group analysts already exists" },
      status: 200,
    });

    const result = await entityService.createGroup("analysts");

    expect(result).toEqual({
      message: "Group analysts already exists",
      status: 200,
    });
  });
});
