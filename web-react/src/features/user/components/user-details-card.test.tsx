import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { UserDetailsCard } from "./user-details-card";

describe("UserDetailsCard", () => {
    const mockUser = {
        username: "testuser",
        display_name: "Test User",
        is_admin: true,
        groups: [
            { id: "1", group_name: "group1" },
            { id: "2", group_name: "group2" }
        ]
    };

    it("renders user details and groups", () => {
        render(<UserDetailsCard currentUser={mockUser as any} />);

        expect(screen.getByText("Test User")).toBeDefined();
        expect(screen.getByText("testuser")).toBeDefined();
        expect(screen.getByText("group1")).toBeDefined();
        expect(screen.getByText("group2")).toBeDefined();
        expect(screen.getByText(/administrator privileges/i)).toBeDefined();
    });

    it("renders 'N/A' and no group message when data is missing", () => {
        const minimalUser = {
            username: "min",
            display_name: "",
            is_admin: false,
            groups: []
        };
        render(<UserDetailsCard currentUser={minimalUser as any} />);

        expect(screen.getByText("N/A")).toBeDefined();
        expect(screen.getByText(/not a member of any groups/i)).toBeDefined();
        expect(screen.queryByText(/administrator privileges/i)).toBeNull();
    });
});
