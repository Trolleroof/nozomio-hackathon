import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlaygroundPanel } from "../components/playground-panel";
import { deployments } from "@crucible/shared/fixtures";

describe("PlaygroundPanel", () => {
  it("sends inference requests through the AnyGPU gateway proxy", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "Deployment health is passing." } }]
      })
    } as Response);

    render(<PlaygroundPanel deployment={deployments[0]} />);
    fireEvent.change(screen.getByLabelText("Test prompt"), {
      target: { value: "Health summary?" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send test request" }));

    expect(await screen.findByText("Deployment health is passing.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/gateway/chat", expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("Health summary?")
    }));
    fetchMock.mockRestore();
  });

  it("shows gateway errors instead of silently swallowing failed inference", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: false,
      json: async () => ({ error: { message: "deployment has no healthy routes" } })
    } as Response);

    render(<PlaygroundPanel deployment={deployments[0]} />);
    fireEvent.click(screen.getByRole("button", { name: "Send test request" }));

    expect(await screen.findByText("deployment has no healthy routes")).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
