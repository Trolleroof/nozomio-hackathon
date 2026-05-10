import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import ProvidersPage from "../../app/providers/page";
import { listProviderCapabilities } from "../lib/crucible-data";

describe("ProvidersPage", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("derives provider status from real configuration and gateway models", async () => {
    vi.stubEnv("MODAL_TOKEN_ID", "token-id");
    vi.stubEnv("MODAL_TOKEN_SECRET", "token-secret");
    vi.stubEnv("VAST_AI_API_KEY", "");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        data: [
          {
            id: "modal-live",
            anygpu: { provider: "modal", health: "healthy", simulated: false }
          }
        ]
      })
    }));

    render(await ProvidersPage());
    expect(screen.getByRole("heading", { name: "Provider status" })).toBeInTheDocument();
    expect(screen.getByText("Live deploy supported")).toBeInTheDocument();
    expect(screen.getByText("Configured but not tested")).toBeInTheDocument();
    expect(screen.getByText("Unsupported")).toBeInTheDocument();
    expect(screen.getByText("Modal")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.getByText("Vast.ai")).toBeInTheDocument();
  });

  it("recognizes the AnyGPU Vast credential alias", async () => {
    vi.stubEnv("VAST_AI_API_KEY", "");
    vi.stubEnv("VAST_API_KEY", "");
    vi.stubEnv("ANYGPU_VAST_API_KEY", "vast-token");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("gateway unavailable")));

    const providers = await listProviderCapabilities();
    const vast = providers.find((provider) => provider.provider === "Vast.ai");

    expect(vast?.status).toBe("configured");
    expect(vast?.supportsDeploy).toBe(true);
    expect(vast?.lastError).toBeUndefined();
  });
});
