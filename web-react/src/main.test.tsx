import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";

// We need to reset modules and re-register mocks inside each test so that
// importing `main.tsx` (which does a top-level `await init()`) uses our mocks
// instead of the real `getRuntimeConfig` implementation that fetches.

let initializeThemeMock: ReturnType<typeof vi.fn>;
let getRuntimeConfigMock: ReturnType<typeof vi.fn>;
let removeTrailingSlashesMock: ReturnType<typeof vi.fn>;
let renderMock: ReturnType<typeof vi.fn>;
let createRootMock: ReturnType<typeof vi.fn>;

describe("main entrypoint", () => {
  let rootEl: HTMLDivElement;

  beforeEach(() => {
    // ensure fresh module import each test
    vi.resetModules();

    // recreate mocks for each test
    initializeThemeMock = vi.fn();
    getRuntimeConfigMock = vi.fn(() =>
      Promise.resolve(((window as any).__RUNTIME_CONFIG__ as any) ?? { basePath: "/", uiPath: "/app/", provider: "p", authenticated: false }),
    );
    removeTrailingSlashesMock = vi.fn((s: string) => s.replace(/\/+$|^$/, "") || "");
    renderMock = vi.fn();
    createRootMock = vi.fn(() => ({ render: renderMock }));

    // register mocks (must be done after resetModules and before importing main)
    vi.mock("./shared/utils/theme-utils.ts", () => ({
      initializeTheme: initializeThemeMock,
    }));

    vi.mock("./shared/services/runtime-config", () => ({
      getRuntimeConfig: getRuntimeConfigMock,
    }));

    vi.mock("./shared/utils/string-utils", () => ({
      removeTrailingSlashes: removeTrailingSlashesMock,
    }));

    vi.mock("react-dom/client", () => ({
      createRoot: createRootMock,
    }));

    // Set up DOM root element expected by main.tsx
    rootEl = document.createElement("div");
    rootEl.id = "root";
    document.body.appendChild(rootEl);

    // Make sure there's no residual runtime config
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    delete window.__RUNTIME_CONFIG__;
  });

  afterEach(() => {
    document.body.removeChild(rootEl);
    vi.restoreAllMocks();
  });

  it("calls initializeTheme, obtains config, calculates basename and renders via createRoot", async () => {
    // Importing main executes the top-level `await init()` that we want to test
    await import("./main.tsx");

    // initializeTheme should have been called
    expect(initializeThemeMock).toHaveBeenCalledTimes(1);

    // getRuntimeConfig should have been awaited and called
    expect(getRuntimeConfigMock).toHaveBeenCalledTimes(1);

    // removeTrailingSlashes should be called with the uiPath from our mocked config
    expect(removeTrailingSlashesMock).toHaveBeenCalledWith("/app/");

    // createRoot should be invoked with the #root element and its render should be called
    expect(createRootMock).toHaveBeenCalledWith(rootEl);
    expect(renderMock).toHaveBeenCalledTimes(1);

    // verify call order roughly: initializeTheme -> getRuntimeConfig -> createRoot
    const callsOrder = [
      initializeThemeMock.mock.invocationCallOrder[0],
      getRuntimeConfigMock.mock.invocationCallOrder[0],
      createRootMock.mock.invocationCallOrder[0],
    ];
    expect(callsOrder[0]).toBeLessThan(callsOrder[1]);
    expect(callsOrder[1]).toBeLessThan(callsOrder[2]);
  });


});
