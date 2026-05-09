import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import ProvidersPage from "../../app/providers/page";

describe("ProvidersPage", () => {
  it("distinguishes live, dry-run, configured, and unsupported providers", () => {
    render(<ProvidersPage />);
    expect(screen.getByRole("heading", { name: "Provider status" })).toBeInTheDocument();
    expect(screen.getByText("Live deploy supported")).toBeInTheDocument();
    expect(screen.getByText("Dry-run/planning supported")).toBeInTheDocument();
    expect(screen.getByText("Configured but not tested")).toBeInTheDocument();
    expect(screen.getByText("Unsupported")).toBeInTheDocument();
  });
});
