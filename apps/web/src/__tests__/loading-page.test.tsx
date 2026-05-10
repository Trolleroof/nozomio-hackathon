import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { vi } from "vitest";

import Loading from "../../app/loading";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard"
}));

describe("Route loading UI", () => {
  it("shows a page switching loading status", () => {
    render(<Loading />);

    expect(screen.getByRole("status", { name: "Loading page" })).toBeInTheDocument();
    expect(screen.getByText("Switching pages")).toBeInTheDocument();
  });
});
