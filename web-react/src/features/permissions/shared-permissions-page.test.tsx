import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SharedPermissionsPage } from "./shared-permissions-page";

const mockUseUser = vi.fn();
const mockUseUserDetails = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => ({ username: "testuser" }),
  Link: ({ children, to, className }: any) => <a href={to} className={className}>{children}</a>,
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

vi.mock("../../core/hooks/use-user-details", () => ({
  useUserDetails: () => mockUseUserDetails(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

vi.mock("./components/normal-permissions-view", () => ({
  NormalPermissionsView: () => <div data-testid="normal-view">Normal View</div>,
}));

vi.mock("./components/regex-permissions-view", () => ({
  RegexPermissionsView: () => <div data-testid="regex-view">Regex View</div>,
}));

vi.mock("../../shared/components/switch", () => ({
    Switch: ({ checked, onChange, label, labelClassName }: any) => (
        <div onClick={() => onChange(!checked)} data-testid="regex-switch" className={labelClassName}>
            {label}
        </div>
    )
}))

vi.mock("../../shared/components/token-info-block", () => ({
    TokenInfoBlock: () => <div>Token Block</div>
}))


describe("SharedPermissionsPage", () => {
    beforeEach(() => {
        mockUseUser.mockReturnValue({
            currentUser: { is_admin: false }
        });
        mockUseUserDetails.mockReturnValue({
            user: null,
            refetch: vi.fn()
        })
    })

  it("renders correctly for read permissions", () => {
    render(<SharedPermissionsPage type="experiments" baseRoute="/users" entityKind="user" />);
    
    expect(screen.getByTestId("page-container")).toHaveAttribute("title", "Permissions for testuser");
    expect(screen.getByTestId("normal-view")).toBeInTheDocument();
  });

  it("toggles regex mode for admin", () => {
    mockUseUser.mockReturnValue({
        currentUser: { is_admin: true }
    });

    render(<SharedPermissionsPage type="experiments" baseRoute="/users" entityKind="user" />);
    
    expect(screen.getByTestId("normal-view")).toBeInTheDocument();
    
    const switchEl = screen.getByTestId("regex-switch");
    fireEvent.click(switchEl);
    
    expect(screen.getByTestId("regex-view")).toBeInTheDocument();
    expect(screen.queryByTestId("normal-view")).not.toBeInTheDocument();
  });
});
