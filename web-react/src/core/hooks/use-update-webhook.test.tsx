import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useUpdateWebhook } from "./use-update-webhook";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as webhookServiceModule from "../services/webhook-service";
import type { ToastContextType } from "../../shared/components/toast/toast-context-val";
import type { Webhook } from "../../shared/types/entity";

vi.mock("../../shared/components/toast/use-toast");
vi.mock("../services/webhook-service");

describe("useUpdateWebhook", () => {
  const mockShowToast = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as ToastContextType);
  });

  it("calls updateWebhook and shows success toast on success", async () => {
    vi.spyOn(webhookServiceModule, "updateWebhook").mockResolvedValue(
      {} as Webhook,
    );

    const { result } = renderHook(() => useUpdateWebhook());

    let success;
    await act(async () => {
      success = await result.current.update(
        "123",
        { name: "New Name" },
        {
          onSuccessMessage: "Success!",
          onErrorMessage: "Error!",
        },
      );
    });

    expect(success).toBe(true);
    expect(webhookServiceModule.updateWebhook).toHaveBeenCalledWith("123", {
      name: "New Name",
    });
    expect(mockShowToast).toHaveBeenCalledWith("Success!", "success");
    expect(result.current.isUpdating).toBe(false);
  });

  it("calls updateWebhook and shows error toast on failure", async () => {
    vi.spyOn(webhookServiceModule, "updateWebhook").mockRejectedValue(
      new Error("API Error"),
    );

    const { result } = renderHook(() => useUpdateWebhook());

    let success;
    await act(async () => {
      success = await result.current.update(
        "123",
        { name: "New Name" },
        {
          onSuccessMessage: "Success!",
          onErrorMessage: "Error!",
        },
      );
    });

    expect(success).toBe(false);
    expect(mockShowToast).toHaveBeenCalledWith("Error!", "error");
    expect(result.current.isUpdating).toBe(false);
  });
});
