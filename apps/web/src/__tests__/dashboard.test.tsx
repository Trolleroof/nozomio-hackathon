import "@testing-library/jest-dom";
import { afterEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import ContextPage from "../../app/context/page";
import DashboardPage from "../../app/dashboard/page";
import DeploymentDetailPage from "../../app/deployments/[id]/page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({
    refresh: vi.fn()
  })
}));

describe("DashboardPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows the protected operational dashboard content without fixture deployments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));
    render(await DashboardPage());
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Active deployments")).toBeInTheDocument();
    expect(screen.getByText("No live deployments found. Start the AnyGPU gateway or deploy a real model to populate this list.")).toBeInTheDocument();
    expect(screen.getByText("Provider status")).toBeInTheDocument();
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("base_url")).toBeInTheDocument();
  });
});

describe("DeploymentDetailPage", () => {
  it("shows a missing deployment state instead of falling back to a fixture", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ data: [] })
    }));

    render(await DeploymentDetailPage({ params: Promise.resolve({ id: "dep_qwen_modal" }) }));
    expect(screen.getByRole("heading", { name: "Deployment not found" })).toBeInTheDocument();
    expect(screen.getByText("No real deployment exists for dep_qwen_modal.")).toBeInTheDocument();
    expect(screen.queryByText("Qwen safe Modal demo")).not.toBeInTheDocument();
  });

  it("shows the deployment operations surface for a real gateway model", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        data: [
          {
            id: "live-chat",
            anygpu: {
              health: "healthy",
              provider: "docker",
              runtime: "vllm",
              simulated: false,
              upstream_url: "http://127.0.0.1:8080"
            }
          }
        ]
      })
    }));

    render(await DeploymentDetailPage({ params: Promise.resolve({ id: "live-chat" }) }));
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Health checks")).toBeInTheDocument();
    expect(screen.getByText("Logs")).toBeInTheDocument();
    expect(screen.getByText("Benchmark")).toBeInTheDocument();
    expect(screen.getByText("Playground")).toBeInTheDocument();
    expect(screen.getByText("Stop deployment")).toBeInTheDocument();
  });
});

describe("ContextPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("does not show cached fixture context when Nia is not configured", async () => {
    vi.stubEnv("NIA_API_KEY", "");
    render(await ContextPage());
    expect(screen.getByText("Indexed sources")).toBeInTheDocument();
    expect(screen.getByText("Recent Nia searches")).toBeInTheDocument();
    expect(screen.getByText("Context snippets used in agent decisions")).toBeInTheDocument();
    expect(screen.getByText("No context snippets yet. Configure NIA_API_KEY or run a search to populate live context.")).toBeInTheDocument();
    expect(screen.queryByText("SkyPilot docs")).not.toBeInTheDocument();
  });
});
