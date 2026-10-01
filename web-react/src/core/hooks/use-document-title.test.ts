import { renderHook } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { pageTitleFor, useDocumentTitle } from "./use-document-title";

describe("pageTitleFor", () => {
  it.each([
    ["/", "Not found · MLflow Access Control"],
    ["/users", "Users · MLflow Access Control"],
    [
      "/users/alice%40example.com/experiments",
      "alice@example.com · Experiments · Users · MLflow Access Control",
    ],
    [
      "/groups/data-science/models",
      "data-science · Models · Groups · MLflow Access Control",
    ],
    [
      "/service-accounts/ci-bot/ai-secrets",
      "ci-bot · AI secrets · Service accounts · MLflow Access Control",
    ],
    ["/service-accounts", "Service accounts · MLflow Access Control"],
    ["/workspaces/team-a", "team-a · Workspaces · MLflow Access Control"],
    ["/experiments/42", "42 · Experiments · MLflow Access Control"],
    ["/ai-gateway/ai-endpoints", "AI endpoints · MLflow Access Control"],
    [
      "/ai-gateway/secrets/openai-key",
      "openai-key · AI secrets · MLflow Access Control",
    ],
    ["/ai-gateway/models/gpt", "gpt · AI models · MLflow Access Control"],
    ["/mcp-servers", "MCP servers · MLflow Access Control"],
    [
      "/mcp-servers/com.example%2Fweather",
      "com.example/weather · MCP servers · MLflow Access Control",
    ],
    [
      "/users/alice/mcp-servers",
      "alice · MCP servers · Users · MLflow Access Control",
    ],
    ["/trash/runs", "Trash · MLflow Access Control"],
    ["/user/tokens", "My account · MLflow Access Control"],
    ["/scim", "SCIM · MLflow Access Control"],
    ["/workspace-rules", "Workspace rules · MLflow Access Control"],
    ["/auth", "Sign in · MLflow Access Control"],
    ["/403", "Access denied · MLflow Access Control"],
    ["/no-such-page", "Not found · MLflow Access Control"],
  ])("%s → %s", (pathname, expected) => {
    expect(pageTitleFor(pathname)).toBe(expected);
  });

  it("keeps a segment that is not valid percent-encoding as it is", () => {
    expect(pageTitleFor("/users/100%")).toBe(
      "100% · Users · MLflow Access Control",
    );
  });
});

describe("useDocumentTitle", () => {
  it("sets document.title for the current route", () => {
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        MemoryRouter,
        { initialEntries: ["/groups"] },
        children,
      );
    renderHook(() => useDocumentTitle(), { wrapper });
    expect(document.title).toBe("Groups · MLflow Access Control");
  });
});
