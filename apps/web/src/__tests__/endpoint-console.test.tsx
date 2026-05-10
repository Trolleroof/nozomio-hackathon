import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EndpointConsole } from "../components/endpoint-console";

describe("EndpointConsole", () => {
  it("shows an animated assistant placeholder while chat is waiting for the endpoint", async () => {
    let resolveResponse!: (response: Response) => void;
    vi.spyOn(global, "fetch").mockReturnValueOnce(
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      })
    );

    render(<EndpointConsole />);
    fireEvent.change(screen.getByPlaceholderText("Message the endpoint"), {
      target: { value: "Ping the runtime" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Ping the runtime")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Endpoint response pending" })).toHaveTextContent("Endpoint is thinking");
    expect(screen.getByRole("button", { name: "Sending message" })).toBeDisabled();

    resolveResponse({
      ok: true,
      json: async () => ({
        choices: [{ message: { content: "Runtime is ready." } }]
      })
    } as Response);

    expect(await screen.findByText("Runtime is ready.")).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
