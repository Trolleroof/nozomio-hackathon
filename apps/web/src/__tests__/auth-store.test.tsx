import { describe, expect, it, vi } from "vitest";

describe("server auth store", () => {
  it("persists signup and login sessions without exposing password hashes", async () => {
    vi.stubEnv("CRUCIBLE_AUTH_STORE_PATH", `/tmp/crucible-auth-${Date.now()}-${Math.random()}.json`);
    const { login, signup } = await import("../lib/server-auth");

    const created = await signup("Judge@Example.com", "correct horse battery staple");
    const session = await login("judge@example.com", "correct horse battery staple");

    expect(created.user).toEqual(expect.objectContaining({
      email: "judge@example.com",
      role: "admin"
    }));
    expect(created.user).not.toHaveProperty("passwordHash");
    expect(session.session.token).toMatch(/^sess_/);
    await expect(login("judge@example.com", "wrong password")).rejects.toThrow("Invalid email or password.");
  });

  it("uses InsForge auth endpoints when a project base URL is configured", async () => {
    vi.stubEnv("INSFORGE_API_BASE_URL", "https://demo.insforge.app");
    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        user: { id: "if_user_1", email: "judge@example.com", role: "authenticated" },
        accessToken: "jwt.access.token",
        refreshToken: "refresh-token"
      })
    } as Response);

    const { signup } = await import("../lib/server-auth");
    const created = await signup("judge@example.com", "correct horse battery staple");

    expect(global.fetch).toHaveBeenCalledWith(
      "https://demo.insforge.app/api/auth/users?client_type=server",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" }
      })
    );
    expect(created.user).toEqual({ id: "if_user_1", email: "judge@example.com", role: "user" });
    expect(created.session.token).toBe("jwt.access.token");
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });
});
