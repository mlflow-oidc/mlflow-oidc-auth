import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import ExperimentsPage from "./experiments-page";
import * as apiUtils from "../../core/services/api-utils";
import * as useAuthModule from "../../core/hooks/use-auth";
import * as workspaceContext from "../../shared/context/use-workspace";
import { _resetPageSizeForTests } from "../../core/hooks/use-page-size";
import { installLocalStorageMock } from "../../tests/local-storage-mock";
import type { ExperimentListItem } from "../../shared/types/entity";

// End to end through the real page, table, usePagedList and paged fetcher; only the HTTP layer
// (requestWithHeaders) is mocked, standing in for the paginating backend.
vi.mock("../../core/services/api-utils", async (importActual) => ({
  ...(await importActual<typeof apiUtils>()),
  requestWithHeaders: vi.fn(),
}));
vi.mock("../../core/hooks/use-auth");
vi.mock("../../shared/context/use-workspace");

installLocalStorageMock();

const ALL: ExperimentListItem[] = Array.from({ length: 45 }, (_, i) => ({
  id: String(i + 1),
  name: `exp-${String(i + 1).padStart(2, "0")}`,
  tags: {},
}));

type Query = { limit?: number; offset?: number; search?: string };

/** A paginating backend: filters by `search`, slices by `limit`/`offset`, reports X-Total-Count. */
function paginatingBackend(sendTotal = true) {
  vi.mocked(apiUtils.requestWithHeaders).mockImplementation(
    (_endpoint, options) => {
      const q = (options?.queryParams ?? {}) as Query;
      const matching = ALL.filter((e) =>
        e.name.toLowerCase().includes((q.search ?? "").toLowerCase()),
      );
      const page =
        !sendTotal || q.limit === undefined
          ? sendTotal
            ? matching
            : ALL // a backend without pagination ignores all three params
          : matching.slice(q.offset ?? 0, (q.offset ?? 0) + q.limit);
      const headers = new Headers(
        sendTotal ? { "X-Total-Count": String(matching.length) } : {},
      );
      return Promise.resolve({ data: page, status: 200, headers });
    },
  );
}

const lastQuery = (): Query =>
  (vi.mocked(apiUtils.requestWithHeaders).mock.lastCall?.[1]?.queryParams ??
    {}) as Query;

const renderPage = () =>
  render(
    <MemoryRouter>
      <ExperimentsPage />
    </MemoryRouter>,
  );

describe("ExperimentsPage server-side pagination", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    _resetPageSizeForTests();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as ReturnType<typeof useAuthModule.useAuth>);
    vi.spyOn(workspaceContext, "useSelectedWorkspace").mockReturnValue(null);
  });

  it("requests the first page and labels the range from X-Total-Count", async () => {
    paginatingBackend();
    renderPage();
    expect(await screen.findByText("exp-01")).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ limit: 20, offset: 0 });
    expect(lastQuery()).not.toHaveProperty("search");
    expect(screen.queryByText("exp-21")).not.toBeInTheDocument();
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "1–20 of 45",
    );
  });

  it("requests the next offset when the page changes", async () => {
    paginatingBackend();
    renderPage();
    await screen.findByText("exp-01");

    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("exp-21")).toBeInTheDocument();
    expect(lastQuery()).toMatchObject({ limit: 20, offset: 20 });
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "21–40 of 45",
    );
  });

  it("sends the search to the server and goes back to page 1", async () => {
    paginatingBackend();
    renderPage();
    await screen.findByText("exp-01");
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("exp-21");

    const input = screen.getByPlaceholderText("Search experiments...");
    fireEvent.change(input, { target: { value: "exp-3" } });
    fireEvent.submit(input);

    await waitFor(() =>
      expect(lastQuery()).toMatchObject({
        limit: 20,
        offset: 0,
        search: "exp-3",
      }),
    );
    expect(await screen.findByText("exp-30")).toBeInTheDocument();
    expect(screen.queryByText("exp-21")).not.toBeInTheDocument();
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "1–10 of 10",
    );
  });

  it("omits limit when All is selected", async () => {
    paginatingBackend();
    renderPage();
    await screen.findByText("exp-01");

    await userEvent.selectOptions(
      screen.getByLabelText("Rows per page"),
      "All",
    );
    expect(await screen.findByText("exp-45")).toBeInTheDocument();
    expect(lastQuery()).not.toHaveProperty("limit");
    expect(lastQuery()).not.toHaveProperty("offset");
    expect(screen.getByTestId("pagination-range")).toHaveTextContent("All 45");
  });

  it("falls back to client-side paging and search without X-Total-Count", async () => {
    paginatingBackend(false);
    renderPage();
    expect(await screen.findByText("exp-01")).toBeInTheDocument();
    expect(screen.queryByText("exp-21")).not.toBeInTheDocument();
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "1–20 of 45",
    );

    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(await screen.findByText("exp-21")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Search experiments...");
    fireEvent.change(input, { target: { value: "exp-4" } });
    fireEvent.submit(input);
    expect(await screen.findByText("exp-45")).toBeInTheDocument();
    expect(screen.queryByText("exp-01")).not.toBeInTheDocument();
    expect(screen.getByTestId("pagination-range")).toHaveTextContent(
      "1–6 of 6",
    );
  });
});
