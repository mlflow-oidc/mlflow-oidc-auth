import { describe, it, expect, vi, beforeEach } from "vitest";
import * as apiUtils from "./api-utils";
import { fetchPagedList, listQueryParams } from "./paged-list";

vi.mock("./api-utils", () => ({ requestWithHeaders: vi.fn() }));

type Item = { name: string };
const items: Item[] = ["alpha", "beta", "Gamma", "delta", "epsilon"].map(
  (name) => ({ name }),
);
const options = {
  extract: (body: Item[]) => body,
  displayKey: (item: Item) => item.name,
};

const respond = (data: Item[], headers: Record<string, string> = {}) =>
  vi.mocked(apiUtils.requestWithHeaders).mockResolvedValue({
    data,
    status: 200,
    headers: new Headers(headers),
  });

describe("listQueryParams", () => {
  it("omits everything for a full-list request", () => {
    expect(listQueryParams({})).toEqual({});
  });

  it("sends limit, offset and search when set", () => {
    expect(listQueryParams({ limit: 20, offset: 40, search: "x" })).toEqual({
      limit: 20,
      offset: 40,
      search: "x",
    });
  });

  it("defaults offset to 0 with a limit and drops an empty search", () => {
    expect(listQueryParams({ limit: 20, search: "" })).toEqual({
      limit: 20,
      offset: 0,
    });
  });
});

describe("fetchPagedList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses X-Total-Count and the body as the page when the server paginates", async () => {
    respond(items.slice(0, 2), { "X-Total-Count": "134" });
    const result = await fetchPagedList(
      "/list",
      { limit: 2, offset: 0, search: "a" },
      { ...options, queryParams: { service: true } },
    );
    expect(result).toEqual({ items: items.slice(0, 2), total: 134 });
    expect(apiUtils.requestWithHeaders).toHaveBeenCalledWith(
      "/list",
      expect.objectContaining({
        method: "GET",
        queryParams: { service: true, limit: 2, offset: 0, search: "a" },
      }),
    );
  });

  it("falls back to local search and slicing when the header is absent", async () => {
    respond(items);
    const result = await fetchPagedList(
      "/list",
      { limit: 2, offset: 2, search: "A" },
      options,
    );
    // alpha, beta, Gamma and delta contain "a"; epsilon does not.
    expect(result.total).toBe(4);
    expect(result.items.map((i) => i.name)).toEqual(["Gamma", "delta"]);
  });

  it("returns the whole list without a limit and without the header", async () => {
    respond(items);
    const result = await fetchPagedList("/list", {}, options);
    expect(result).toEqual({ items, total: 5 });
  });

  it("ignores a malformed X-Total-Count", async () => {
    respond(items, { "X-Total-Count": "lots" });
    const result = await fetchPagedList(
      "/list",
      { limit: 2, offset: 0 },
      options,
    );
    expect(result.total).toBe(5);
    expect(result.items).toHaveLength(2);
  });
});
