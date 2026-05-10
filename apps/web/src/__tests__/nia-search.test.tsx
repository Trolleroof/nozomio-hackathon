import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "../../app/api/nia/search/route";
import { ContextPanel } from "../components/context-panel";
import { LogPanel } from "../components/log-panel";

const snippets = [
  {
    id: "ctx_fixture",
    source: "nia://fixture",
    title: "Fixture context",
    excerpt: "Cached fixture context.",
    usedFor: "Default context",
    searchedAt: "2026-05-09T16:00:00.000Z"
  }
];

const prices = [
  {
    id: "nia_price_0",
    provider: "RunPod",
    accelerator: "NVIDIA L4",
    region: "US",
    availability: "available",
    pricePerHourUsd: 0.44,
    priceText: "$0.44/hr",
    source: "nia://pricing/runpod",
    searchedAt: "2026-05-09T20:00:00.000Z"
  }
];

describe("Nia search API route", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("does not return cached fixture snippets when Nia is unconfigured", async () => {
    vi.stubEnv("NIA_API_KEY", " ");

    const response = await POST(
      new Request("http://localhost/api/nia/search", {
        method: "POST",
        body: JSON.stringify({ query: "Qwen 7B deployment" })
      })
    );
    const body = await response.json();

    expect(body.connected).toBe(false);
    expect(body.snippets).toEqual([]);
    expect(body.prices).toEqual([]);
    expect(JSON.stringify(body)).not.toContain("Fixture context");
  });

  it("uses the server-side Nia key and normalizes live search results", async () => {
    vi.stubEnv("NIA_API_KEY", "test-nia-token");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        sources: [
          {
            title: "Live Qwen recipe",
            source: "nia://repo/recipes/qwen",
            text: "Use one economical GPU first, then verify OpenAI-compatible health checks."
          },
          {
            title: "RunPod prices",
            source: "nia://pricing/runpod",
            provider: "RunPod",
            gpu_name: "NVIDIA L4",
            region: "US",
            price_per_hour_usd: 0.44,
            availability: "available",
            text: "RunPod NVIDIA L4 is available at $0.44/hr in US."
          }
        ]
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      new Request("http://localhost/api/nia/search", {
        method: "POST",
        body: JSON.stringify({ query: "Qwen 7B deployment" })
      })
    );
    const body = await response.json();

    expect(fetchMock).toHaveBeenCalledWith(
      "https://apigcp.trynia.ai/v2/search",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-nia-token" })
      })
    );
    expect(body.connected).toBe(true);
    expect(body.snippets).toEqual([
      {
        id: "nia_0",
        source: "nia://repo/recipes/qwen",
        title: "Live Qwen recipe",
        excerpt: "Use one economical GPU first, then verify OpenAI-compatible health checks.",
        usedFor: "Nia search: Qwen 7B deployment",
        searchedAt: expect.any(String)
      },
      {
        id: "nia_1",
        source: "nia://pricing/runpod",
        title: "RunPod prices",
        excerpt: "RunPod NVIDIA L4 is available at $0.44/hr in US.",
        usedFor: "Nia search: Qwen 7B deployment",
        searchedAt: expect.any(String)
      }
    ]);
    expect(body.prices).toEqual([
      {
        id: "nia_price_1",
        provider: "RunPod",
        accelerator: "NVIDIA L4",
        region: "US",
        availability: "available",
        pricePerHourUsd: 0.44,
        priceText: "$0.44/hr",
        source: "nia://pricing/runpod",
        searchedAt: expect.any(String)
      }
    ]);
    expect(JSON.stringify(body)).not.toContain("test-nia-token");
  });

  it("extracts provider prices from Nia prose answers", async () => {
    vi.stubEnv("NIA_API_KEY", "test-nia-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        answer: "Current provider prices: Modal L4 $0.80/hr; Vast.ai H100 $4.50/hr available; Vultr A100 $2.40/hr in ewr."
      })
    }));

    const response = await POST(
      new Request("http://localhost/api/nia/search", {
        method: "POST",
        body: JSON.stringify({ query: "provider prices" })
      })
    );
    const body = await response.json();

    expect(body.prices).toEqual([
      expect.objectContaining({ provider: "Modal", accelerator: "L4", priceText: "$0.80/hr" }),
      expect.objectContaining({ provider: "Vast.ai", accelerator: "H100", priceText: "$4.50/hr", availability: "available" }),
      expect.objectContaining({ provider: "Vultr", accelerator: "A100", region: "ewr", priceText: "$2.40/hr" })
    ]);
  });
});

describe("ContextPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows connected Nia status and can replace cached snippets with live search results", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        connected: true,
        snippets: [
          {
            id: "nia_0",
            source: "nia://repo/provider-notes",
            title: "Provider notes",
            excerpt: "Vast.ai is connected and approval is still required before launch.",
            usedFor: "Nia search: provider status",
            searchedAt: "2026-05-09T20:00:00.000Z"
          }
        ],
        prices: [
          {
            id: "nia_price_1",
            provider: "Vast.ai",
            accelerator: "H100",
            priceText: "$4.50/hr",
            source: "nia://pricing/vast",
            searchedAt: "2026-05-09T20:00:00.000Z"
          }
        ]
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ContextPanel niaConnected prices={prices} snippets={snippets} />);

    expect(screen.getByText("Nia is connected and grounding deployment decisions in live indexed context.")).toBeInTheDocument();
    expect(screen.getByText("Live provider prices")).toBeInTheDocument();
    expect(screen.getByText("RunPod")).toBeInTheDocument();
    expect(screen.getByText("$0.44/hr")).toBeInTheDocument();
    expect(screen.getByText("What Nia proved for this deployment")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search Nia context"), { target: { value: "provider status" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("Provider notes")).toBeInTheDocument());
    expect(screen.getAllByText("provider status")).toHaveLength(2);
    expect(screen.getByText("Vast.ai")).toBeInTheDocument();
    expect(screen.getByText("cited in plan")).toBeInTheDocument();
    expect(screen.queryByText("Fixture context")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/nia/search",
      expect.objectContaining({ method: "POST" })
    );
  });
});

describe("LogPanel", () => {
  it("redacts Nia API keys from deployment logs", () => {
    render(
      <LogPanel
        logs={[
          {
            id: "log_1",
            timestamp: "2026-05-09T20:00:00.000Z",
            level: "info",
            message: "NIA_API_KEY=nk_testsecret should never be displayed"
          }
        ]}
      />
    );

    expect(screen.getByText("[redacted] should never be displayed")).toBeInTheDocument();
    expect(screen.queryByText(/nk_testsecret/)).not.toBeInTheDocument();
  });
});
