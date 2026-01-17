import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ServiceAccountsPage from "./service-accounts-page";

const mockUseAllServiceAccounts = vi.fn();
const mockUseCurrentUser = vi.fn();
const mockCreateUser = vi.fn();
const mockDeleteUser = vi.fn();
const mockShowToast = vi.fn();

vi.mock("../../core/hooks/use-all-accounts", () => ({
  useAllServiceAccounts: () => mockUseAllServiceAccounts(),
}));

vi.mock("../../core/hooks/use-current-user", () => ({
  useCurrentUser: () => mockUseCurrentUser(),
}));

vi.mock("../../core/services/user-service", () => ({
  createUser: (...args: any[]) => mockCreateUser(...args),
  deleteUser: (...args: any[]) => mockDeleteUser(...args),
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => ({
    searchTerm: "",
    submittedTerm: "",
    handleInputChange: vi.fn(),
    handleSearchSubmit: vi.fn(),
    handleClearSearch: vi.fn(),
  }),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading }: any) => isLoading ? <div>Loading...</div> : null
}));

vi.mock("../../shared/components/entity-list-table", () => ({
    EntityListTable: ({ data, columns }: any) => (
        <div data-testid="sa-list">
            {data.map((item: any) => (
                <div key={item.username}>
                    {item.username}
                    {/* Render delete action */}
                     {columns.find((c: any) => c.header === "Actions")?.render(item)}
                </div>
            ))}
        </div>
    )
}));

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({ title, onClick }: any) => <button onClick={onClick} title={title}>{title}</button>
}));

vi.mock("./components/create-service-account-modal", () => ({
    CreateServiceAccountModal: ({ isOpen, onSave }: any) => isOpen ? (
        <div data-testid="create-modal">
            <button onClick={() => onSave({ name: "newsa", display_name: "New SA", is_admin: false })}>Confirm Create</button>
        </div>
    ) : null
}));

describe("ServiceAccountsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAllServiceAccounts.mockReturnValue({
        allServiceAccounts: ["sa1"],
        isLoading: false,
        refresh: vi.fn()
    });
    mockUseCurrentUser.mockReturnValue({
        currentUser: { is_admin: true }
    });
  });

  it("renders correctly", () => {
    render(<ServiceAccountsPage />);
    expect(screen.getByText("sa1")).toBeInTheDocument();
  });

  it("opens create modal", () => {
    render(<ServiceAccountsPage />);
    
    fireEvent.click(screen.getByText("Create Service Account"));
    expect(screen.getByTestId("create-modal")).toBeInTheDocument();
  });

  it("creates service account", async () => {
    mockCreateUser.mockResolvedValue({});
    render(<ServiceAccountsPage />);
    
    fireEvent.click(screen.getByText("Create Service Account"));
    fireEvent.click(screen.getByText("Confirm Create"));
    
    await waitFor(() => {
        expect(mockCreateUser).toHaveBeenCalledWith({
            username: "newsa", 
            display_name: "New SA", 
            is_admin: false, 
            is_service_account: true
        });
    });
  });
});
