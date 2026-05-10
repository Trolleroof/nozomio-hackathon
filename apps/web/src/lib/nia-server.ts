import fs from "node:fs";
import path from "node:path";

import type { NiaContextSnippet } from "@crucible/shared/crucible-contract";

const NIA_DEFAULT_BASE_URL = "https://apigcp.trynia.ai/v2";
const NIA_SNIPPET_LIMIT = 5;

interface RawNiaSearchResult {
  [key: string]: unknown;
}

export interface NiaSearchResponse {
  connected: boolean;
  error?: string;
  snippets: NiaContextSnippet[];
}

export function hasNiaApiKey() {
  return Boolean(getServerEnv("NIA_API_KEY"));
}

export async function searchNia(query: string): Promise<NiaSearchResponse> {
  const apiKey = getServerEnv("NIA_API_KEY");
  if (!apiKey) {
    return {
      connected: false,
      error: "Nia is not configured.",
      snippets: []
    };
  }

  const baseUrl = (getServerEnv("NIA_API_BASE_URL") || NIA_DEFAULT_BASE_URL).replace(/\/$/, "");
  try {
    const contextSnippets = await searchNiaContexts(baseUrl, apiKey, query);
    if (contextSnippets.length > 0) {
      return {
        connected: true,
        snippets: contextSnippets
      };
    }

    const response = await fetch(`${baseUrl}/search`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        mode: "query",
        messages: [{ role: "user", content: query }],
        search_mode: "unified",
        include_sources: true,
        fast_mode: true,
        max_tokens: 1200
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(15000)
    });

    if (!response.ok) {
      return {
        connected: true,
        error: `Nia search failed with HTTP ${response.status}.`,
        snippets: []
      };
    }

    const body = await response.json();
    const snippets = normalizeNiaSearchResponse(body, query, {
      idPrefix: "nia",
      sourceFallback: "nia://search",
      titleFallback: "Nia result",
      usedForPrefix: "Nia search"
    });
    return {
      connected: true,
      snippets
    };
  } catch (error) {
    return {
      connected: true,
      error: `Nia search unavailable (${safeErrorMessage(error)}).`,
      snippets: []
    };
  }
}

export function normalizeNiaSearchResponse(
  body: RawNiaSearchResult,
  query: string,
  options: {
    idPrefix?: string;
    sourceFallback?: string;
    titleFallback?: string;
    usedForPrefix?: string;
  } = {}
): NiaContextSnippet[] {
  const now = new Date().toISOString();
  const candidates = candidateItems(body);
  const normalizedOptions = {
    idPrefix: options.idPrefix ?? "nia",
    sourceFallback: options.sourceFallback ?? "nia://search",
    titleFallback: options.titleFallback ?? "Nia result",
    usedForPrefix: options.usedForPrefix ?? "Nia search"
  };
  const snippets = candidates
    .map((candidate, index) => normalizeCandidate(candidate, index, query, now, normalizedOptions))
    .filter((snippet): snippet is NiaContextSnippet => Boolean(snippet))
    .slice(0, NIA_SNIPPET_LIMIT);

  if (snippets.length > 0) {
    return snippets;
  }

  const answer = firstText(body, ["answer", "content", "text", "summary"]);
  if (!answer) {
    return [];
  }
  return [
    {
      id: `${normalizedOptions.idPrefix}_answer`,
      source: normalizedOptions.sourceFallback,
      title: `${normalizedOptions.titleFallback} answer`,
      excerpt: clean(answer, 360),
      usedFor: `${normalizedOptions.usedForPrefix}: ${query}`,
      searchedAt: now
    }
  ];
}

async function searchNiaContexts(baseUrl: string, apiKey: string, query: string) {
  const semanticUrl = new URL(`${baseUrl}/contexts/semantic-search`);
  semanticUrl.searchParams.set("q", query);
  semanticUrl.searchParams.set("limit", String(NIA_SNIPPET_LIMIT));
  semanticUrl.searchParams.set("include_highlights", "false");

  const semantic = await fetchNiaContextSearch(semanticUrl, apiKey);
  if (semantic.length > 0) {
    return semantic;
  }

  const textUrl = new URL(`${baseUrl}/contexts/search`);
  textUrl.searchParams.set("q", query);
  textUrl.searchParams.set("limit", String(NIA_SNIPPET_LIMIT));
  return fetchNiaContextSearch(textUrl, apiKey);
}

async function fetchNiaContextSearch(url: URL, apiKey: string) {
  try {
    const response = await fetch(url.toString(), {
      method: "GET",
      headers: {
        Authorization: `Bearer ${apiKey}`
      },
      cache: "no-store",
      signal: AbortSignal.timeout(15000)
    });
    if (!response.ok) {
      return [];
    }
    const body = await response.json();
    return normalizeNiaSearchResponse(body, url.searchParams.get("q") || "", {
      idPrefix: "nia_context",
      sourceFallback: "nia://contexts/search",
      titleFallback: "Nia context",
      usedForPrefix: "Nia context search"
    });
  } catch {
    return [];
  }
}

function normalizeCandidate(
  candidate: unknown,
  index: number,
  query: string,
  searchedAt: string,
  options: {
    idPrefix: string;
    sourceFallback: string;
    titleFallback: string;
    usedForPrefix: string;
  }
): NiaContextSnippet | null {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
    return null;
  }
  const record = candidate as RawNiaSearchResult;
  const excerpt = firstText(record, ["snippet", "excerpt", "text", "content", "body", "answer", "summary"]);
  if (!excerpt) {
    return null;
  }
  const rawId = firstText(record, ["id", "context_id", "_id"]);
  const source = firstText(record, ["source", "url", "uri", "repository", "file_path", "path", "source_id"]);
  return {
    id: rawId ? `${options.idPrefix}_${cleanId(rawId)}` : `${options.idPrefix}_${index}`,
    source: clean(source || (rawId ? `nia://context/${rawId}` : options.sourceFallback), 160),
    title: clean(
      firstText(record, ["title", "name", "display_name", "file", "path"]) ||
        nestedText(record, "source", ["display_name", "file_path", "document_name", "url"]) ||
        `${options.titleFallback} ${index + 1}`,
      120
    ),
    excerpt: clean(excerpt, 360),
    usedFor: `${options.usedForPrefix}: ${query}`,
    searchedAt
  };
}

function candidateItems(body: RawNiaSearchResult): unknown[] {
  for (const key of ["contexts", "sources", "results", "documents", "matches", "items", "data"]) {
    const value = body[key];
    if (Array.isArray(value)) {
      return value;
    }
    if (value && typeof value === "object") {
      const nested = candidateItems(value as RawNiaSearchResult);
      if (nested.length > 0) {
        return nested;
      }
    }
  }
  return [];
}

function firstText(record: RawNiaSearchResult, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
    if (value && typeof value === "object" && !Array.isArray(value)) {
      const nested = firstText(value as RawNiaSearchResult, [
        "title",
        "name",
        "display_name",
        "file_path",
        "url",
        "path",
        "text",
        "content",
        "snippet"
      ]);
      if (nested) {
        return nested;
      }
    }
  }
  return undefined;
}

function cleanId(value: string) {
  return clean(value, 80).replace(/[^A-Za-z0-9_-]/g, "_");
}

function nestedText(record: RawNiaSearchResult, key: string, nestedKeys: string[]) {
  const value = record[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  return firstText(value as RawNiaSearchResult, nestedKeys);
}

function clean(value: string, maxLength: number) {
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLength) {
    return cleaned;
  }
  return `${cleaned.slice(0, maxLength - 3).trimEnd()}...`;
}

function safeErrorMessage(error: unknown) {
  const message = error instanceof Error ? error.message : "unknown error";
  return clean(message.replace(/nk_[A-Za-z0-9_-]+/g, "[redacted-nia-key]"), 180);
}

function getServerEnv(name: string) {
  if (Object.prototype.hasOwnProperty.call(process.env, name)) {
    return process.env[name]?.trim() || undefined;
  }
  if (process.env.NODE_ENV === "test") {
    return undefined;
  }

  for (const envPath of candidateEnvPaths()) {
    const value = readEnvValue(envPath, name);
    if (value) {
      return value;
    }
  }
  return undefined;
}

function candidateEnvPaths() {
  return [
    path.join(process.cwd(), ".env.local"),
    path.join(process.cwd(), ".env"),
    path.join(process.cwd(), "..", "..", ".env.local"),
    path.join(process.cwd(), "..", "..", ".env")
  ];
}

function readEnvValue(envPath: string, name: string) {
  if (!fs.existsSync(envPath)) {
    return undefined;
  }
  const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const [rawKey, ...rest] = line.startsWith("export ") ? line.slice(7).split("=") : line.split("=");
    if (rawKey.trim() !== name) {
      continue;
    }
    const value = rest.join("=").trim();
    return value.replace(/^['"]|['"]$/g, "");
  }
  return undefined;
}
