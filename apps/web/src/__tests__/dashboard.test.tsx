import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import ContextPage from "../../app/context/page";
import DashboardPage from "../../app/dashboard/page";
import DeploymentDetailPage from "../../app/deployments/[id]/page";

describe("DashboardPage", () => {
  it("shows the protected operational dashboard content", () => {
    render(<DashboardPage />);
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(screen.getByText("Active deployments")).toBeInTheDocument();
    expect(screen.getByText("Provider status")).toBeInTheDocument();
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("base_url")).toBeInTheDocument();
    expect(screen.getByText("Quick deployment")).toBeInTheDocument();
  });
});

describe("DeploymentDetailPage", () => {
  it("shows the deployment operations surface", () => {
    render(<DeploymentDetailPage />);
    expect(screen.getByText("Endpoint")).toBeInTheDocument();
    expect(screen.getByText("Health checks")).toBeInTheDocument();
    expect(screen.getByText("Logs")).toBeInTheDocument();
    expect(screen.getByText("Benchmark")).toBeInTheDocument();
    expect(screen.getByText("Playground")).toBeInTheDocument();
    expect(screen.getByText("Stop deployment")).toBeInTheDocument();
  });
});

describe("ContextPage", () => {
  it("shows cached Nia context visibility", () => {
    render(<ContextPage />);
    expect(screen.getByText("Indexed sources")).toBeInTheDocument();
    expect(screen.getByText("Recent Nia searches")).toBeInTheDocument();
    expect(screen.getByText("Context snippets used in agent decisions")).toBeInTheDocument();
    expect(screen.getByText("SkyPilot docs")).toBeInTheDocument();
    expect(screen.getByText("vLLM docs")).toBeInTheDocument();
    expect(screen.getByText("Modal vLLM docs")).toBeInTheDocument();
    expect(screen.getByText("known working recipes")).toBeInTheDocument();
  });
});
