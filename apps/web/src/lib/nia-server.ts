import fs from "node:fs";
import path from "node:path";

import type { NiaContextSnippet } from "@crucible/shared/crucible-contract";
import { contextSnippets } from "@crucible/shared/fixtures";

const NIA_DEFAULT_BASE_URL = "https://apigcp.trynia.ai/v2";

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
      error: "Nia is not configured; showing cached context.",
      snippets: contextSnippets
    };
  }

  const baseUrl = (getServerEnv("NIA_API_BASE_URL") || NIA_DEFAULT_BASE_URL).replace(/\/$/, "");
  try {
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
        error: `Nia search failed with HTTP ${response.status}; showing cached context.`,
        snippets: contextSnippets
      };
    }

    const body = await response.json();
    const snippets = normalizeNiaSearchResponse(body, query);
    return {
      connected: true,
      snippets: snippets.length > 0 ? snippets : contextSnippets
    };
  } catch {
    return {
      connected: true,
      error: "Nia search unavailable; showing cached context.",
      snippets: contextSnippets
    };
  }
}

export function normalizeNiaSearchResponse(body: RawNiaSearchResult, query: string): NiaContextSnippet[] {
  const now = new Date().toISOString();
  const candidates = candidateItems(body);
  const snippets = candidates
    .map((candidate, index) => normalizeCandidate(candidate, index, query, now))
    .filter((snippet): snippet is NiaContextSnippet => Boolean(snippet))
    .slice(0, 5);

  if (snippets.length > 0) {
    return snippets;
  }

  const answer = firstText(body, ["answer", "content", "text", "summary"]);
  if (!answer) {
    return [];
  }
  return [
    {
      id: "nia_answer",
      source: "nia://search",
      title: "Nia answer",
      excerpt: clean(answer, 360),
      usedFor: `Nia search: ${query}`,
      searchedAt: now
    }
  ];
}

function normalizeCandidate(
  candidate: unknown,
  index: number,
  query: string,
  searchedAt: string
): NiaContextSnippet | null {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
    return null;
  }
  const record = candidate as RawNiaSearchResult;
  const excerpt = firstText(record, ["snippet", "excerpt", "text", "content", "body", "answer", "summary"]);
  if (!excerpt) {
    return null;
  }
  return {
    id: `nia_${index}`,
    source: clean(firstText(record, ["source", "url", "uri", "repository", "file_path", "path", "source_id"]) || "nia://search", 160),
    title: clean(
      firstText(record, ["title", "name", "display_name", "file", "path"]) ||
        nestedText(record, "source", ["display_name", "file_path", "document_name", "url"]) ||
        `Nia result ${index + 1}`,
      120
    ),
    excerpt: clean(excerpt, 360),
    usedFor: `Nia search: ${query}`,
    searchedAt
  };
}

function candidateItems(body: RawNiaSearchResult): unknown[] {
  for (const key of ["sources", "results", "documents", "matches", "items", "data"]) {
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

function getServerEnv(name: string) {
  if (process.env[name]) {
    return process.env[name];
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
