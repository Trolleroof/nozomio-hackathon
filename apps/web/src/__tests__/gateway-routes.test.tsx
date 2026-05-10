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

  it("proxies model requests with gateway auth and dashboard user agent", async () => {
    vi.resetModules();
    vi.stubEnv("ANYGPU_GATEWAY_BASE_URL", "https://gateway.example/v1");
    vi.stubEnv("ANYGPU_GATEWAY_API_KEY", "gateway-key");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ data: [{ id: "qwen" }] })
    });
    vi.stubGlobal("fetch", fetchMock);

    const { GET } = await import("../../app/api/gateway/models/route");
    const response = await GET();
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body.models).toEqual([{ id: "qwen" }]);
    expect(fetchMock).toHaveBeenCalledWith("https://gateway.example/v1/models", expect.objectContaining({
      headers: {
        Authorization: "Bearer gateway-key",
        "User-Agent": "Crucible-Dashboard/0.1"
      }
    }));
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("rejects chat requests when no runtime is configured", async () => {
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

    expect(response.status).toBe(503);
    expect(body.error).toBe("No live deployment endpoint is configured.");
    vi.unstubAllEnvs();
  });
});
