import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ServiceAccountSourceFields } from "./service-account-source-fields";

describe("ServiceAccountSourceFields", () => {
  it("shows a source whose provider is no longer configured as it is, not as Internal", () => {
    render(
      <ServiceAccountSourceFields
        sources={[
          {
            id: "internal",
            display_name: "Internal (issued access tokens only)",
            type: "internal",
          },
        ]}
        source="old-idp"
        subject=""
        onSourceChange={vi.fn()}
        onSubjectChange={vi.fn()}
        idPrefix="t"
      />,
    );

    expect(screen.getByLabelText("Signs in with")).toHaveValue("old-idp");
    expect(
      screen.getByRole("option", { name: "old-idp (not configured)" }),
    ).toBeInTheDocument();
  });
});
