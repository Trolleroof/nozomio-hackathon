import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EndpointConsole } from "../components/endpoint-console";

describe("EndpointConsole", () => {
  it("defaults chat to the newest ready deployment and lets operators switch live deployments", async () => {
    render(<EndpointConsole deployments={[
      {
        id: "dep_old",
        planId: "plan_old",
        name: "Older model",
        modelId: "older/model",
        provider: "Vast.ai",
        accelerator: "NVIDIA L4",
        status: "ready",
        endpointUrl: "/api/gateway",
        createdAt: "2026-05-09T20:00:00.000Z",
        updatedAt: "2026-05-09T20:00:00.000Z",
        logs: [],
        healthChecks: [],
        context: []
      },
      {
        id: "dep_new",
        planId: "plan_new",
        name: "Newest model",
        modelId: "newest/model",
        provider: "Vultr",
        accelerator: "NVIDIA A16",
        status: "ready",
        endpointUrl: "/api/gateway",
        createdAt: "2026-05-09T22:00:00.000Z",
        updatedAt: "2026-05-09T22:00:00.000Z",
        logs: [],
        healthChecks: [],
        context: []
      },
      {
        id: "dep_failed",
        planId: "plan_failed",
        name: "Failed model",
        modelId: "failed/model",
        provider: "Modal",
        accelerator: "NVIDIA L4",
        status: "failed",
        createdAt: "2026-05-09T23:00:00.000Z",
        updatedAt: "2026-05-09T23:00:00.000Z",
        logs: [],
        healthChecks: [],
        context: []
      }
    ]} />);

    expect(screen.getByLabelText("Live deployment")).toHaveValue("dep_new");
    expect(screen.getByRole("link", { name: "Open deployment" })).toHaveAttribute("href", "/deployments/dep_new");
    fireEvent.change(screen.getByLabelText("Live deployment"), { target: { value: "dep_old" } });
    expect(screen.getByRole("link", { name: "Open deployment" })).toHaveAttribute("href", "/deployments/dep_old");
    expect(screen.queryByRole("option", { name: /Failed model/ })).not.toBeInTheDocument();
  });

  it("shows an animated assistant placeholder while chat is waiting for the endpoint", async () => {
    let resolveResponse!: (response: Response) => void;
    vi.spyOn(global, "fetch").mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      })
    );

    render(<EndpointConsole />);
    fireEvent.change(screen.getByPlaceholderText("Message the endpoint"), {
      target: { value: "Ping the runtime" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Ping the runtime")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Endpoint response pending" })).toHaveTextContent("Endpoint is thinking");
    expect(screen.getByRole("button", { name: "Sending message" })).toBeDisabled();

    resolveResponse({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "Runtime is ready." } }]
      })
    } as Response);

    expect(await screen.findByText("Runtime is ready.")).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
