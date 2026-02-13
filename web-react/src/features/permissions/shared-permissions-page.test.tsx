import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SharedPermissionsPage } from "./shared-permissions-page";

const mockUseUser =
  vi.fn<
    () => { currentUser: { is_admin: boolean; username: string } | null }
  >();
const mockUseUserDetails =
  vi.fn<() => { user: unknown; refetch: () => void }>();
const mockUseRuntimeConfig = vi.fn<() => { gen_ai_gateway_enabled: boolean }>();

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string): string | null => store[key] || null,
    setItem: (key: string, value: string): void => {
      store[key] = value.toString();
    },
    clear: () => {
      store = {};
    },
    removeItem: (key: string) => {
      delete store[key];
    },
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

const mockUseParams = vi.fn<() => { username?: string; groupName?: string }>();
vi.mock("react-router", () => ({
  useParams: () => mockUseParams(),
  Link: ({
    children,
    to,
    className,
  }: {
    children: React.ReactNode;
    to: string;
    className?: string;
  }) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

vi.mock("../../core/hooks/use-user-details", () => ({
  useUserDetails: () => mockUseUserDetails(),
}));

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title: string;
  }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("./components/normal-permissions-view", () => ({
  NormalPermissionsView: () => <div data-testid="normal-view">Normal View</div>,
}));

vi.mock("./components/regex-permissions-view", () => ({
  RegexPermissionsView: () => <div data-testid="regex-view">Regex View</div>,
}));

vi.mock("../../shared/components/switch", () => ({
  Switch: ({
    checked,
    onChange,
    label,
    labelClassName,
  }: {
    checked: boolean;
    onChange: (checked: boolean) => void;
    label: string;
    labelClassName?: string;
  }) => (
    <div
      onClick={() => onChange(!checked)}
      data-testid="regex-switch"
      className={labelClassName}
    >
      {label}
    </div>
  ),
}));

vi.mock("../../shared/components/token-info-block", () => ({
  TokenInfoBlock: () => <div>Token Block</div>,
}));

describe("SharedPermissionsPage", () => {
  beforeEach(() => {
    localStorage.clear();
    mockUseParams.mockReturnValue({ username: "testuser" });
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: false, username: "testuser" },
    });
    mockUseUserDetails.mockReturnValue({
      user: null,
      refetch: vi.fn(),
    });
    mockUseRuntimeConfig.mockReturnValue({
      gen_ai_gateway_enabled: false,
    });
  });

  it("renders correctly for read permissions", () => {
    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    expect(screen.getByTestId("page-container")).toHaveAttribute(
      "title",
      "Permissions for testuser",
    );
    expect(screen.getByTestId("normal-view")).toBeInTheDocument();
  });

  it("toggles regex mode for admin", () => {
    mockUseUser.mockReturnValue({
      currentUser: {
        is_admin: true,
        username: "",
      },
    });

    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    expect(screen.getByTestId("normal-view")).toBeInTheDocument();

    const switchEl = screen.getByTestId("regex-switch");
    fireEvent.click(switchEl);

    expect(screen.getByTestId("regex-view")).toBeInTheDocument();
    expect(screen.queryByTestId("normal-view")).not.toBeInTheDocument();
  });

  it("loads regex mode from localStorage", () => {
    localStorage.setItem("_mlflow_is_regex_mode", "true");
    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );
    expect(screen.getByTestId("regex-view")).toBeInTheDocument();
  });

  it("saves regex mode to localStorage", () => {
    mockUseUser.mockReturnValue({
      currentUser: {
        is_admin: true,
        username: "",
      },
    });
    localStorage.setItem("_mlflow_is_regex_mode", "false");
    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    const switchEl = screen.getByTestId("regex-switch");
    fireEvent.click(switchEl);

    expect(localStorage.getItem("_mlflow_is_regex_mode")).toBe("true");
  });

  it("shows Endpoints tab when gen_ai_gateway_enabled is true", () => {
    mockUseRuntimeConfig.mockReturnValue({
      gen_ai_gateway_enabled: true,
    });
    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    expect(screen.getByText("Endpoints")).toBeInTheDocument();
  });

  it("hides Endpoints tab when gen_ai_gateway_enabled is false", () => {
    mockUseRuntimeConfig.mockReturnValue({
      gen_ai_gateway_enabled: false,
    });
    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    expect(screen.queryByText("Endpoints")).not.toBeInTheDocument();
  });

  it("encodes entityName in tab links", () => {
    mockUseParams.mockReturnValue({
      username: "alice@example.com",
    });

    render(
      <SharedPermissionsPage
        type="experiments"
        baseRoute="/users"
        entityKind="user"
      />,
    );

    const experimentLink = screen.getByText("Experiments");
    expect(experimentLink.getAttribute("href")).toContain(
      "/users/alice@example.com/experiments",
    );

    const modelsLink = screen.getByText("Models");
    expect(modelsLink.getAttribute("href")).toContain(
      "/users/alice@example.com/models",
    );
  });
});
