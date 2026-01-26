import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import GroupPermissionsPage from "./group-permissions-page";

import type { PermissionType, PermissionKind } from "../../shared/types/entity";

vi.mock("../permissions/shared-permissions-page", () => ({
  SharedPermissionsPage: ({
    type,
    baseRoute,
    entityKind,
  }: {
    type: PermissionType;
    baseRoute: string;
    entityKind: PermissionKind;
  }) => (
    <div data-testid="shared-permissions-page">
      {type} - {baseRoute} - {entityKind}
    </div>
  ),
}));

describe("GroupPermissionsPage", () => {
  it("renders SharedPermissionsPage with correct props", () => {
    render(<GroupPermissionsPage type="experiments" />);

    const page = screen.getByTestId("shared-permissions-page");
    expect(page).toHaveTextContent("experiments");
    expect(page).toHaveTextContent("/groups");
    expect(page).toHaveTextContent("group");
  });
});
