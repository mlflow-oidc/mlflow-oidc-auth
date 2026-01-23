
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserProvider } from "./user-provider";
import * as useCurrentUserModule from "../hooks/use-current-user";

vi.mock("../hooks/use-current-user");

describe("UserProvider", () => {
    it("provides user context to children", () => {
        vi.spyOn(useCurrentUserModule, "useCurrentUser").mockReturnValue({
            currentUser: { username: "testuser", is_admin: false } as any,
            isLoading: false,
            error: null,
            refresh: vi.fn(),
        });

        render(
            <UserProvider>
                <div data-testid="child">Child</div>
            </UserProvider>
        );

        expect(screen.getByTestId("child")).toBeInTheDocument();
    });
});
