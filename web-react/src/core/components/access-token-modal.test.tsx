import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AccessTokenModal } from "./access-token-modal";

const mockRefresh = vi.fn();
const mockShowToast = vi.fn();
const mockHttp = vi.fn();

vi.mock("../hooks/use-user", () => ({
  useUser: () => ({ refresh: mockRefresh }),
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../services/http", () => ({
  http: (...args: any[]) => mockHttp(...args),
}));

// Mock clipboard
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
});

describe("AccessTokenModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders correctly", () => {
    render(<AccessTokenModal onClose={() => {}} username="testuser" />);
    expect(screen.getByText("Generate Access Token for testuser")).toBeInTheDocument();
  });

  it("handles token generation success", async () => {
    mockHttp.mockResolvedValue({ token: "generated-token" });

    render(
      <AccessTokenModal 
        onClose={() => {}} 
        username="testuser" 
        onTokenGenerated={() => {}}
      />
    );
    
    // Fill date if needed, but it should have default
    // Click request button
    const requestBtn = screen.getByText("Request Token");
    fireEvent.click(requestBtn);
    
    await waitFor(() => {
      expect(mockHttp).toHaveBeenCalled();
    });
    
    expect(screen.getByDisplayValue("generated-token")).toBeInTheDocument();
    expect(mockShowToast).toHaveBeenCalledWith("Access token generated successfully!", "success");
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("handles token generation failure", async () => {
    mockHttp.mockRejectedValue(new Error("API Error"));

    render(<AccessTokenModal onClose={() => {}} username="testuser" />);
    
    const requestBtn = screen.getByText("Request Token");
    fireEvent.click(requestBtn);
    
    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith("Failed to generate access token", "error");
    });
  });

   it("copies token to clipboard", async () => {
    mockHttp.mockResolvedValue({ token: "generated-token" });

    render(<AccessTokenModal onClose={() => {}} username="testuser" />);
    
    // Generate token first
    fireEvent.click(screen.getByText("Request Token"));
    await waitFor(() => expect(screen.getByDisplayValue("generated-token")).toBeInTheDocument());
    
    // Click copy button
    const copyBtn = screen.getByTitle("Copy Access Token");
    fireEvent.click(copyBtn);
    
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("generated-token");
    // Feedback
    await waitFor(() => expect(screen.getByText("Copied!")).toBeInTheDocument());
  });
});
