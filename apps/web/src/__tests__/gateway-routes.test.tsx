import { describe, expect, it, vi } from "vitest";

describe("gateway routes", () => {
  it("returns a built-in demo model when no external gateway is configured", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");

    const { GET } = await import("../../app/api/gateway/models/route");
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.baseUrl).toBe("/api/gateway");
    expect(body.models[0]).toEqual(expect.objectContaining({
      id: "Qwen/Qwen2.5-7B-Instruct",
      anygpu: expect.objectContaining({
        provider: "Crucible demo",
        simulated: true
      })
    }));
    vi.unstubAllEnvs();
  });

  it("answers chat requests through the built-in demo gateway when no runtime is configured", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");

    const { POST } = await import("../../app/api/gateway/chat/route");
    const response = await POST(new Request("http://localhost/api/gateway/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "Qwen/Qwen2.5-7B-Instruct",
        messages: [{ role: "user", content: "Is the deployment ready?" }]
      })
    }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.choices[0].message.content).toContain("Qwen/Qwen2.5-7B-Instruct");
    expect(body.choices[0].message.content).toContain("ready");
    expect(body.anygpu.simulated).toBe(true);
    vi.unstubAllEnvs();
  });
});
