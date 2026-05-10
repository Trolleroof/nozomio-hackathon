import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
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

  it("lets a first-time user choose a model and objective before opening the real deployment planner", () => {
    render(<OnboardingPage />);

    fireEvent.click(screen.getByRole("radio", { name: /Mistral 7B Instruct/i }));
    fireEvent.click(screen.getByRole("radio", { name: /Reliability/i }));
    fireEvent.click(screen.getByRole("button", { name: "Continue to planner" }));

    expect(pushMock).toHaveBeenCalledWith("/deployments/new?modelId=mistralai%2FMistral-7B-Instruct-v0.3&objective=reliable");
    expect(localStorage.getItem("crucible:onboarding-complete")).toBe("true");
    expect(localStorage.getItem("crucible:onboarding-launch")).toBeNull();
  });
});

describe("DashboardPage onboarding launch", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("ignores stale first-run launch state instead of showing a fake spin-up", async () => {
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

    expect(screen.queryByText("Live first model launch")).not.toBeInTheDocument();
    expect(screen.queryByText("mistralai/Mistral-7B-Instruct-v0.3")).not.toBeInTheDocument();
    expect(screen.getByText("No live deployments found. Start the AnyGPU gateway or deploy a real model to populate this list.")).toBeInTheDocument();
  });
});
