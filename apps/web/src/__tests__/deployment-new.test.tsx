import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import NewDeploymentPage from "../../app/deployments/new/page";

describe("NewDeploymentPage", () => {
  it("creates a safe approval-required plan for Qwen 7B", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: "plan_test",
        prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
        modelId: "Qwen/Qwen2.5-7B-Instruct",
        objective: "cheapest",
        recommendation: {
          provider: "Vast.ai",
          accelerator: "NVIDIA L4",
          estimatedHourlyUsd: 0.27,
          reason: "The request fits a single economical L4-class GPU and keeps paid launch behind explicit approval.",
          uncertainty: "Final memory fit, exact hourly price, and endpoint readiness depend on live provider capacity."
        },
        approvalRequired: true,
        approvalReason: "Approval required before launching paid GPU resources from a personal agent.",
        status: "generated",
        createdAt: "2026-05-09T22:00:00.000Z"
      })
    } as Response);

    render(<NewDeploymentPage />);
    const prompt = screen.getByLabelText("Deployment request");
    fireEvent.change(prompt, {
      target: { value: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
    expect(await screen.findByText("Approval required")).toBeInTheDocument();
    expect(screen.getByText("Vast.ai")).toBeInTheDocument();
    expect(screen.getByText("Qwen/Qwen2.5-7B-Instruct")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("shows session memory insights when the plan used previous runs", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: "plan_memory",
        prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
        modelId: "Qwen/Qwen2.5-7B-Instruct",
        objective: "cheapest",
        recommendation: {
          provider: "Modal",
          accelerator: "NVIDIA L4",
          estimatedHourlyUsd: 0.8,
          reason: "Past session memory says Vast.ai L4 failed health checks, so Modal is safer for this retry.",
          uncertainty: "Nia context and session memory can change before launch."
        },
        approvalRequired: true,
        approvalReason: "Approval required before launching paid GPU resources from a personal agent.",
        status: "generated",
        createdAt: "2026-05-09T22:00:00.000Z",
        memoryInsights: ["Vast.ai L4 failed health checks; prefer Modal for this model next time."]
      })
    } as Response);

    render(<NewDeploymentPage />);
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));

    expect(await screen.findByText("Session memory")).toBeInTheDocument();
    expect(screen.getByText("Vast.ai L4 failed health checks; prefer Modal for this model next time.")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("lets users remember a failed plan outcome for future agent runs", async () => {
    vi.spyOn(global, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "plan_memory_write",
          prompt: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required.",
          modelId: "Qwen/Qwen2.5-7B-Instruct",
          objective: "cheapest",
          recommendation: {
            provider: "Modal",
            accelerator: "NVIDIA L4",
            estimatedHourlyUsd: 0.8,
            reason: "Modal is safer for this retry.",
            uncertainty: "Cold-start still needs a live health check."
          },
          approvalRequired: true,
          approvalReason: "Approval required before launching paid GPU resources from a personal agent.",
          status: "generated",
          createdAt: "2026-05-09T22:00:00.000Z"
        })
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          memoryInsights: ["Remembered failed Modal run for future planning."]
        })
      } as Response);

    render(<NewDeploymentPage />);
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
    await screen.findByText("Modal");
    fireEvent.click(screen.getByRole("button", { name: "Remember failure" }));

    expect(await screen.findByText("Saved to session memory.")).toBeInTheDocument();
    expect(global.fetch).toHaveBeenLastCalledWith("/api/crucible/memory", expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("\"outcome\":\"failed\"")
    }));
    vi.restoreAllMocks();
  });
});
