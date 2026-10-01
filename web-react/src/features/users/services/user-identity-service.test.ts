import { describe, it, expect, vi, beforeEach } from "vitest";
import * as apiUtils from "../../../core/services/api-utils";
import {
  listUserIdentities,
  unbindUserIdentity,
} from "./user-identity-service";

vi.mock("../../../core/services/api-utils");

describe("user-identity-service", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists a user's identities", async () => {
    vi.mocked(apiUtils.request).mockResolvedValue([]);
    await listUserIdentities("a b");
    expect(apiUtils.request).toHaveBeenCalledWith(
      "/api/2.0/mlflow/users/a%20b/identities",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("sends the subject in the query, where a slash is safe", async () => {
    vi.mocked(apiUtils.request).mockResolvedValue({ deleted: 1 });
    await unbindUserIdentity("ci-bot", {
      provider_id: "ci",
      subject: "repo:org/app:ref:refs/heads/main",
    });
    expect(apiUtils.request).toHaveBeenCalledWith(
      "/api/2.0/mlflow/users/ci-bot/identities?provider_id=ci&subject=repo%3Aorg%2Fapp%3Aref%3Arefs%2Fheads%2Fmain",
      { method: "DELETE" },
    );
  });
});
