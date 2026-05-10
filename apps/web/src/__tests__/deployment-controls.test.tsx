import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const refreshMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: refreshMock
  })
}));

import { DeploymentControls } from "../components/deployment-controls";

describe("DeploymentControls", () => {
  it("stops a ready deployment through the control-plane API", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        deployment: {
          id: "dep_live",
          status: "stopped"
        }
      })
    } as Response);

    render(<DeploymentControls deploymentId="dep_live" initialStatus="ready" />);
    fireEvent.click(screen.getByRole("button", { name: "Stop deployment" }));

    expect(await screen.findByRole("status", { name: "Stop request in progress" })).toHaveTextContent("Stopping deployment");
    await waitFor(() => expect(refreshMock).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith("/api/crucible/deployments/dep_live/stop", expect.objectContaining({
      method: "POST"
    }));
    expect(screen.getByText("Deployment stopped.")).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
