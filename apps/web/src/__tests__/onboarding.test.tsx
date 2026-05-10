import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "../../app/dashboard/page";
import OnboardingPage from "../../app/onboarding/page";

const pushMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({
    push: pushMock
  })
}));

describe("OnboardingPage", () => {
  beforeEach(() => {
    pushMock.mockClear();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("lets a first-time user choose a model and reliability objective before launching to the dashboard", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: "plan_onboarding",
        prompt: "Spin up Mistral-7B-Instruct optimized for reliability.",
        modelId: "mistralai/Mistral-7B-Instruct-v0.3",
        objective: "reliable",
        recommendation: {
          provider: "Modal",
          accelerator: "NVIDIA A10G",
          estimatedHourlyUsd: 1.1,
          reason: "Modal keeps the first run on the most reliable live path.",
          uncertainty: "Cold-start health still needs a live check."
        },
        approvalRequired: true,
        approvalReason: "Approval required before launching paid GPU resources.",
        status: "generated",
        createdAt: "2026-05-09T22:00:00.000Z"
      })
    } as Response);

    render(<OnboardingPage />);

    fireEvent.click(screen.getByRole("radio", { name: /Mistral 7B Instruct/i }));
    fireEvent.click(screen.getByRole("radio", { name: /Reliability/i }));
    fireEvent.click(screen.getByRole("button", { name: "Launch model" }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/dashboard"));
    expect(global.fetch).toHaveBeenCalledWith("/api/crucible/plan", expect.objectContaining({
      method: "POST",
      body: expect.stringContaining("\"objective\":\"reliable\"")
    }));
    expect(localStorage.getItem("crucible:onboarding-launch")).toContain("mistralai/Mistral-7B-Instruct-v0.3");
  });
});

describe("DashboardPage onboarding launch", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("shows the selected first-run model as a live spin-up on the dashboard", async () => {
    localStorage.setItem("crucible:onboarding-launch", JSON.stringify({
      id: "launch_onboarding",
      planId: "plan_onboarding",
      name: "Mistral 7B first run",
      modelId: "mistralai/Mistral-7B-Instruct-v0.3",
      objective: "reliable",
      provider: "Modal",
      accelerator: "NVIDIA A10G",
      estimatedHourlyUsd: 1.1,
      status: "provisioning",
      createdAt: "2026-05-09T22:00:00.000Z"
    }));

    render(await DashboardPage());

    expect(await screen.findByText("Live first model launch")).toBeInTheDocument();
    expect(screen.getByText("mistralai/Mistral-7B-Instruct-v0.3")).toBeInTheDocument();
    expect(screen.getByText("Optimizing for reliability")).toBeInTheDocument();
    expect(screen.getAllByText("Provisioning").length).toBeGreaterThan(0);
  });
});
