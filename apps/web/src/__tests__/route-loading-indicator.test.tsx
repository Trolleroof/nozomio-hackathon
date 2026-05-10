import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import { RouteLoadingIndicator } from "@/components/route-loading-indicator";

let pathname = "/dashboard";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname
}));

describe("RouteLoadingIndicator", () => {
  it("shows loading feedback after a same-app page link is clicked", () => {
    render(
      <>
        <RouteLoadingIndicator />
        <a href="/providers" onClick={(event) => event.preventDefault()}>
          Providers
        </a>
      </>
    );

    fireEvent.click(screen.getByRole("link", { name: "Providers" }));

    expect(screen.getByRole("status", { name: "Loading page" })).toBeInTheDocument();
    expect(screen.getByText("Loading page")).toBeInTheDocument();
  });
});
