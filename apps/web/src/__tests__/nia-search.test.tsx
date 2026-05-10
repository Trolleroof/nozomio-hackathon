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
      }
    ]);
    expect(JSON.stringify(body)).not.toContain("test-nia-token");
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
        ]
      })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ContextPanel niaConnected snippets={snippets} />);

    expect(screen.getByText("Nia is connected. Search live indexed context for deployment decisions.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search Nia context"), { target: { value: "provider status" } });
    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(screen.getByText("Provider notes")).toBeInTheDocument());
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
