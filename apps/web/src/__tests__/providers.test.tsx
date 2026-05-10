import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";

import ProvidersPage from "../../app/providers/page";

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
});
