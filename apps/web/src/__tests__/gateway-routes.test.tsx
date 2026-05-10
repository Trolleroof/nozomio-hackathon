import { describe, expect, it, vi } from "vitest";

describe("gateway routes", () => {
  it("returns no models when no external gateway is configured", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");

    const { GET } = await import("../../app/api/gateway/models/route");
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.ok).toBe(false);
    expect(body.baseUrl).toBe("");
    expect(body.models).toEqual([]);
    expect(body.error).toBe("No live AnyGPU gateway is configured.");
    vi.unstubAllEnvs();
  });

  it("returns a quick demo chat response when no runtime is configured", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "");
    vi.stubEnv("INSFORGE_API_BASE_URL", "");

    const { POST } = await import("../../app/api/gateway/chat/route");
    const response = await POST(new Request("http://localhost/api/gateway/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "Qwen/Qwen2.5-7B-Instruct",
        messages: [{ role: "user", content: "Summarize the deployment health in one sentence." }]
      })
    }));
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.choices[0].message.content).toContain("Deployment health is passing");
    expect(body.backend.source).toBe("serverless-demo");
    vi.unstubAllEnvs();
  });
});
