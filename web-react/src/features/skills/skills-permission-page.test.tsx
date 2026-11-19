import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import SkillsPermissionPage from "./skills-permission-page";
import { useSkillUserPermissions } from "../../core/hooks/use-skill-user-permissions";
import { useSkillGroupPermissions } from "../../core/hooks/use-skill-group-permissions";

vi.mock("../../core/hooks/use-skill-user-permissions");
vi.mock("../../core/hooks/use-skill-group-permissions");
vi.mock("../permissions/components/entity-permissions-manager", () => ({
  EntityPermissionsManager: (props: { resourceType: string }) => (
    <div data-testid="permissions-manager">{props.resourceType}</div>
  ),
}));

const idle = {
  isLoading: false,
  error: null,
  permissions: [],
  refresh: vi.fn(),
};

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/skills/:name" element={<SkillsPermissionPage />} />
        <Route path="/skills/" element={<SkillsPermissionPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("SkillsPermissionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useSkillUserPermissions).mockReturnValue(idle);
    vi.mocked(useSkillGroupPermissions).mockReturnValue(idle);
  });

  it("decodes the encoded slash and loads the skill's grants", () => {
    renderAt("/skills/@acme%2Freviewer");

    expect(
      screen.getByText("Permissions for Skill @acme/reviewer"),
    ).toBeInTheDocument();
    expect(useSkillUserPermissions).toHaveBeenCalledWith({
      name: "@acme/reviewer",
    });
    expect(useSkillGroupPermissions).toHaveBeenCalledWith({
      name: "@acme/reviewer",
    });
    expect(screen.getByTestId("permissions-manager")).toHaveTextContent(
      "skills",
    );
  });

  it("requires a name", () => {
    renderAt("/skills/");
    expect(screen.getByText("Skill name is required.")).toBeInTheDocument();
  });
});
