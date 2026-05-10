import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { vi } from "vitest";

import NewDeploymentPage from "../../app/deployments/new/page";

describe("NewDeploymentPage", () => {
  it("starts from model selection, three objectives, and optional intent notes", () => {
    render(<NewDeploymentPage />);

    expect(screen.queryByLabelText("Deployment request")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Model")).toHaveValue("Qwen/Qwen2.5-7B-Instruct");
    expect(screen.getByLabelText("Hugging Face link or model ID")).toHaveValue("");
    expect(screen.getByLabelText("Optional notes")).toHaveValue("");
    expect(screen.getAllByRole("radio", { name: /Cheapest|Most reliable|Lowest latency/ })).toHaveLength(3);
    expect(screen.queryByRole("radio", { name: "Balanced" })).not.toBeInTheDocument();
  });

  it("submits the picked model, selected objective, and optional notes as LLM intent", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: "plan_custom",
        prompt: "Deploy NousResearch/Hermes-3-Llama-3.1-8B with reliable objective. Notes: keep one fallback warm",
        modelId: "NousResearch/Hermes-3-Llama-3.1-8B",
        objective: "reliable",
        recommendation: {
          provider: "SkyPilot",
          accelerator: "NVIDIA L4",
          estimatedHourlyUsd: 0.8,
          reason: "Reliability wins, with approval gated before launch.",
          uncertainty: "Provider capacity may change."
        },
        approvalRequired: true,
        approvalReason: "Approval required before launching paid GPU resources from a personal agent.",
        status: "generated",
        createdAt: "2026-05-09T22:00:00.000Z"
      })
    } as Response);

    render(<NewDeploymentPage />);
    fireEvent.change(screen.getByLabelText("Hugging Face link or model ID"), {
      target: { value: "https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B" }
    });
    fireEvent.click(screen.getByRole("radio", { name: "Most reliable" }));
    fireEvent.change(screen.getByLabelText("Optional notes"), {
      target: { value: "keep one fallback warm" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));

    await screen.findByText("SkyPilot");
    expect(global.fetch).toHaveBeenCalledWith("/api/crucible/plan", expect.objectContaining({
      body: JSON.stringify({
        modelId: "NousResearch/Hermes-3-Llama-3.1-8B",
        objective: "reliable",
        notes: "keep one fallback warm"
      })
    }));
    vi.restoreAllMocks();
  });

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
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
    expect(await screen.findByText("Approval required")).toBeInTheDocument();
    expect(screen.getByText("Vast.ai")).toBeInTheDocument();
    expect(screen.getByText("Qwen/Qwen2.5-7B-Instruct")).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("shows an animated deployment planning state while generating", async () => {
    let resolveResponse!: (response: Response) => void;
    vi.spyOn(global, "fetch").mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      })
    );

    render(<NewDeploymentPage />);
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));

    expect(await screen.findByRole("status", { name: "Deployment plan generation in progress" })).toHaveTextContent(
      "Generating plan"
    );
    expect(screen.getByRole("button", { name: "Generating plan" })).toBeDisabled();

    resolveResponse({
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

    expect(await screen.findByText("Vast.ai")).toBeInTheDocument();
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
