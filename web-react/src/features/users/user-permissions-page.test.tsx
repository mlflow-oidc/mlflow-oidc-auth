import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import UserPermissionsPage from "./user-permissions-page";

vi.mock("../permissions/shared-permissions-page", () => ({
  SharedPermissionsPage: ({ type, baseRoute, entityKind }: any) => (
    <div data-testid="shared-permissions-page">
      {type} - {baseRoute} - {entityKind}
    </div>
  ),
}));

describe("UserPermissionsPage", () => {
  it("renders SharedPermissionsPage with correct props", () => {
    render(<UserPermissionsPage type="experiments" />);

    const page = screen.getByTestId("shared-permissions-page");
    expect(page).toHaveTextContent("experiments");
    expect(page).toHaveTextContent("/users");
    expect(page).toHaveTextContent("user");
  });
});
