import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";

import AgentPage from "../../app/agent/page";

describe("AgentPage", () => {
  it("shows MCP, CLI, token, and approval failure examples", () => {
    render(<AgentPage />);
    expect(screen.getByRole("heading", { name: "Agent access" })).toBeInTheDocument();
    expect(screen.getByText("MCP server")).toBeInTheDocument();
    expect(screen.getByText(/npx -y mcp-remote/)).toBeInTheDocument();
    expect(screen.getByText("API token")).toBeInTheDocument();
    expect(screen.getByText("crucible_plan_deployment")).toBeInTheDocument();
    expect(screen.getByText("Approval required before launching GPU resources.")).toBeInTheDocument();
  });
});
