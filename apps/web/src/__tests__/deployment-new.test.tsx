import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import NewDeploymentPage from "../../app/deployments/new/page";

describe("NewDeploymentPage", () => {
  it("creates a safe approval-required plan for Qwen 7B", async () => {
    render(<NewDeploymentPage />);
    const prompt = screen.getByLabelText("Deployment request");
    fireEvent.change(prompt, {
      target: { value: "Deploy Qwen 7B cheaply. Avoid multi-GPU unless required." }
    });
    fireEvent.click(screen.getByRole("button", { name: "Generate plan" }));
    expect(await screen.findByText("Approval required")).toBeInTheDocument();
    expect(screen.getByText("Modal")).toBeInTheDocument();
    expect(screen.getByText("Qwen/Qwen2.5-7B-Instruct")).toBeInTheDocument();
  });
});
