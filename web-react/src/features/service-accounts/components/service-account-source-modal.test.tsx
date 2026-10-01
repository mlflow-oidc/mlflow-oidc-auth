import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ServiceAccountSourceModal } from "./service-account-source-modal";
import * as service from "../services/service-account-source-service";
import * as useToastModule from "../../../shared/components/toast/use-toast";
import type { ToastContextType } from "../../../shared/components/toast/toast-context-val";

vi.mock("../../../shared/components/toast/use-toast");
vi.mock(
  "../services/service-account-source-service",
  async (importOriginal) => ({
    ...(await importOriginal<typeof service>()),
    setServiceAccountSource: vi.fn(),
  }),
);

const SOURCES = [
  {
    id: "internal",
    display_name: "Internal (issued access tokens only)",
    type: "internal",
  },
  { id: "ci", display_name: "CI workloads", type: "oidc" },
];

describe("ServiceAccountSourceModal", () => {
  const onSaved = vi.fn();
  const onClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: vi.fn(),
      removeToast: vi.fn(),
    } as unknown as ToastContextType);
    vi.mocked(service.setServiceAccountSource).mockResolvedValue({
      username: "ci-bot",
      service_account_source: "ci",
    });
  });

  it("points an internal account at a provider, with a subject, warning that its tokens go", async () => {
    render(
      <ServiceAccountSourceModal
        username="ci-bot"
        currentSource="internal"
        sources={SOURCES}
        onClose={onClose}
        onSaved={onSaved}
      />,
    );
    fireEvent.change(screen.getByLabelText("Signs in with"), {
      target: { value: "ci" },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "access tokens issued for this account will be revoked",
    );
    fireEvent.change(screen.getByLabelText("Subject (optional)"), {
      target: { value: "repo:o/a:ref:main" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(service.setServiceAccountSource).toHaveBeenCalledWith(
        "ci-bot",
        "ci",
        "repo:o/a:ref:main",
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it("offers no subject for an internal account", () => {
    render(
      <ServiceAccountSourceModal
        username="ci-bot"
        currentSource="ci"
        sources={SOURCES}
        onClose={onClose}
        onSaved={onSaved}
      />,
    );
    fireEvent.change(screen.getByLabelText("Signs in with"), {
      target: { value: "internal" },
    });

    expect(screen.queryByLabelText("Subject (optional)")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("renders nothing without an account", () => {
    const { container } = render(
      <ServiceAccountSourceModal
        username={null}
        currentSource={null}
        sources={SOURCES}
        onClose={onClose}
        onSaved={onSaved}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
