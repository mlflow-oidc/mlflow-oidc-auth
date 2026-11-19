import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router";
import SkillsPage from "./skills-page";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchSkillsPage } from "../../core/services/skill-service";
import type { SkillListItem } from "../../shared/types/entity";

const mockListSource = vi.fn();
const mockUsePagedList = vi.fn();
vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search = "") => {
    mockUsePagedList(fetchPage, search);
    const { skills, isLoading, error, refresh } = mockListSource() as {
      skills: SkillListItem[];
      isLoading: boolean;
      error: Error | null;
      refresh: () => void;
    };
    return pagedListState(
      skills.filter((s) => s.name.toLowerCase().includes(search.toLowerCase())),
      { isLoading, error, refresh },
    );
  },
}));

const skills: SkillListItem[] = [
  {
    name: "@acme/reviewer",
    organization: "acme",
    skill_name: "reviewer",
    latest_version: 3,
  },
  { name: "linter", organization: "", skill_name: "linter" },
];

const renderPage = () =>
  render(
    <MemoryRouter>
      <SkillsPage />
    </MemoryRouter>,
  );

describe("SkillsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", () => {
    mockListSource.mockReturnValue({
      skills: [],
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText("Loading skills...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockListSource.mockReturnValue({
      skills: [],
      isLoading: false,
      error: new Error("boom"),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/Error: boom/i)).toBeInTheDocument();
  });

  it("links each skill to its permissions page, keeping the slash in one segment", () => {
    mockListSource.mockReturnValue({
      skills,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();

    expect(
      screen.getByRole("link", { name: "@acme/reviewer" }),
    ).toHaveAttribute("href", "/skills/@acme%2Freviewer");
    expect(screen.getByText("acme")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("searches through the paged fetcher", () => {
    mockListSource.mockReturnValue({
      skills,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();

    const input = screen.getByPlaceholderText("Search skills...");
    fireEvent.change(input, { target: { value: "lint" } });
    fireEvent.submit(input);

    expect(mockUsePagedList).toHaveBeenLastCalledWith(fetchSkillsPage, "lint");
    expect(screen.getByText("linter")).toBeInTheDocument();
    expect(screen.queryByText("@acme/reviewer")).not.toBeInTheDocument();
  });
});
