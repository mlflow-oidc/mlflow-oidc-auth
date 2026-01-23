import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ServiceAccountPermissionPage from "./service-account-permission-page";

vi.mock("../permissions/shared-permissions-page", () => ({
  SharedPermissionsPage: ({ type, baseRoute, entityKind }: any) => (
    <div data-testid="shared-permissions-page">
      {type} - {baseRoute} - {entityKind}
    </div>
  ),
}));

describe("ServiceAccountPermissionPage", () => {
  it("renders SharedPermissionsPage with correct props", () => {
    render(<ServiceAccountPermissionPage type="experiments" />);

    const page = screen.getByTestId("shared-permissions-page");
    expect(page).toHaveTextContent("experiments");
    expect(page).toHaveTextContent("/service-accounts");
    expect(page).toHaveTextContent("user"); // Currently reusing 'user' entity kind in implementation
  });
});
