import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "../../app/login/page";
import SignupPage from "../../app/signup/page";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push
  })
}));

function authConfigResponse(providers: string[] = []) {
  return {
    ok: true,
    json: async () => ({
      requireEmailVerification: false,
      passwordMinLength: 8,
      verifyEmailMethod: "code",
      resetPasswordMethod: "code",
      oAuthProviders: providers
    })
  } as Response;
}

describe("auth pages", () => {
  beforeEach(() => {
    push.mockClear();
    vi.restoreAllMocks();
  });

  it("shows animated login feedback while credentials are being checked", async () => {
    vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(authConfigResponse())
      .mockReturnValueOnce(new Promise<Response>(() => {}));

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "judge@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("status", { name: "Login in progress" })).toHaveTextContent("Checking credentials");
    expect(screen.getByRole("button", { name: "Logging in" })).toBeDisabled();
  });

  it("shows animated signup feedback while creating an account", async () => {
    vi.spyOn(global, "fetch")
      .mockResolvedValueOnce(authConfigResponse())
      .mockReturnValueOnce(new Promise<Response>(() => {}));

    render(<SignupPage />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "judge@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery staple" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("status", { name: "Account creation in progress" })).toHaveTextContent(
      "Creating secure session"
    );
    expect(screen.getByRole("button", { name: "Creating account" })).toBeDisabled();
  });

  it("shows enabled InsForge OAuth provider links on login when configured", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(authConfigResponse(["google", "github"]));

    render(<LoginPage />);

    expect(await screen.findByRole("link", { name: "Continue with Google" })).toHaveAttribute(
      "href",
      "/api/auth/oauth/google?next=%2Fdashboard"
    );
    expect(screen.getByRole("link", { name: "Continue with GitHub" })).toHaveAttribute(
      "href",
      "/api/auth/oauth/github?next=%2Fdashboard"
    );
  });

  it("uses the onboarding return path for signup OAuth", async () => {
    vi.spyOn(global, "fetch").mockResolvedValueOnce(authConfigResponse(["google"]));

    render(<SignupPage />);

    expect(await screen.findByRole("link", { name: "Continue with Google" })).toHaveAttribute(
      "href",
      "/api/auth/oauth/google?next=%2Fonboarding"
    );
  });
});
