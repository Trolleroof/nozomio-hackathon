import fs from "node:fs";
import path from "node:path";

import type { NiaContextSnippet, NiaProviderPrice } from "@crucible/shared/crucible-contract";

const NIA_DEFAULT_BASE_URL = "https://apigcp.trynia.ai/v2";
export const NIA_PROVIDER_PRICE_QUERY =
  "Find current hourly GPU prices per provider/platform for Modal, RunPod, Vast.ai, Vultr, Lambda Cloud, CoreWeave, SkyPilot, Tensorlake, and any other indexed AnyGPU providers. Include provider, GPU or instance type, region when available, availability, and USD per hour.";

interface RawNiaSearchResult {
  [key: string]: unknown;
}

export interface NiaSearchResponse {
  connected: boolean;
  error?: string;
  snippets: NiaContextSnippet[];
  prices: NiaProviderPrice[];
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
      snippets: [],
      prices: []
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
        error: `Nia search failed with HTTP ${response.status}.`,
        snippets: [],
        prices: []
      };
    }

    const body = await response.json();
    const snippets = normalizeNiaSearchResponse(body, query);
    const prices = normalizeNiaProviderPrices(body, query);
    return {
      connected: true,
      snippets,
      prices
    };
  } catch (error) {
    return {
      connected: true,
      error: `Nia search unavailable (${safeErrorMessage(error)}).`,
      snippets: [],
      prices: []
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

export function normalizeNiaProviderPrices(body: RawNiaSearchResult, query: string): NiaProviderPrice[] {
  const now = new Date().toISOString();
  const candidates = candidateItems(body);
  const records = candidates.flatMap((candidate, index) => normalizePriceCandidate(candidate, index, query, now));
  const answer = firstText(body, ["answer", "content", "text", "summary"]);
  if (answer) {
    records.push(...extractPricesFromText(answer, "nia://search", query, now, records.length));
  }

  const seen = new Set<string>();
  return records
    .filter((record) => {
      const key = [
        record.provider.toLowerCase(),
        record.accelerator?.toLowerCase() ?? "",
        record.region?.toLowerCase() ?? "",
        record.pricePerHourUsd ?? record.priceText.toLowerCase(),
        sourceHost(record.source)
      ].join("|");
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 24);
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

function normalizePriceCandidate(
  candidate: unknown,
  index: number,
  query: string,
  searchedAt: string
): NiaProviderPrice[] {
  if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
    return [];
  }
  const record = candidate as RawNiaSearchResult;
  const source = clean(firstText(record, ["source", "url", "uri", "repository", "file_path", "path", "source_id"]) || "nia://search", 160);
  const title = firstText(record, ["title", "name", "display_name", "file", "path"]) ?? "";
  const excerpt = firstText(record, ["snippet", "excerpt", "text", "content", "body", "answer", "summary"]) ?? "";
  const pricePerHourUsd = firstNumber(record, [
    "pricePerHourUsd",
    "price_per_hour_usd",
    "price_per_hour",
    "price_per_hr",
    "pricePerHr",
    "hourly_price",
    "hourlyUsd",
    "hourly_usd",
    "cost_per_hour",
    "dph_total",
    "price"
  ]);
  const provider = providerName(
    directText(record, ["provider", "platform", "vendor", "cloud", "provider_name"]) ||
      providerFromText(`${title} ${excerpt} ${source}`)
  );
  const accelerator =
    cleanOptional(directText(record, ["accelerator", "gpu", "gpu_name", "gpuName", "gpu_type", "instance_type", "machine_type", "plan", "sku"]), 80) ||
    acceleratorFromText(`${title} ${excerpt}`);
  const region = cleanOptional(directText(record, ["region", "location", "zone", "datacenter", "country"]), 48) || regionFromText(excerpt);
  const availability = normalizeAvailability(directText(record, ["availability", "available", "capacity", "capacity_status", "status"])) || availabilityFromText(excerpt);

  const records: NiaProviderPrice[] = [];
  if (provider && typeof pricePerHourUsd === "number") {
    records.push({
      id: `nia_price_${index}`,
      provider,
      accelerator,
      region,
      availability,
      pricePerHourUsd,
      priceText: formatHourlyPrice(pricePerHourUsd),
      source,
      searchedAt
    });
  }

  records.push(...extractPricesFromText(`${title}\n${excerpt}`, source, query, searchedAt, index * 10));
  return records;
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

function directText(record: RawNiaSearchResult, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return undefined;
}

function firstNumber(record: RawNiaSearchResult, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      const match = value.match(/\d+(?:\.\d+)?/);
      if (match) {
        return Number(match[0]);
      }
    }
  }
  return undefined;
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

function extractPricesFromText(
  text: string,
  source: string,
  query: string,
  searchedAt: string,
  offset: number
): NiaProviderPrice[] {
  const chunks = text
    .split(/\n|[•*]\s+|;\s+/)
    .map((chunk) => chunk.trim())
    .filter(Boolean);
  const records: NiaProviderPrice[] = [];

  chunks.forEach((chunk, chunkIndex) => {
    const provider = providerName(providerFromText(chunk));
    if (!provider) {
      return;
    }
    for (const match of chunk.matchAll(/(?:\$|USD\s*)\s*(\d+(?:\.\d+)?)\s*(?:\/\s*(?:hr|hour|h)|per\s+hour|hourly)?|\b(\d+(?:\.\d+)?)\s*USD\s*(?:\/\s*(?:hr|hour|h)|per\s+hour)?/gi)) {
      const value = Number(match[1] ?? match[2]);
      if (!Number.isFinite(value)) {
        continue;
      }
      records.push({
        id: `nia_price_text_${offset}_${chunkIndex}_${records.length}`,
        provider,
        accelerator: acceleratorFromText(chunk),
        region: regionFromText(chunk),
        availability: availabilityFromText(chunk),
        pricePerHourUsd: value,
        priceText: formatHourlyPrice(value),
        source,
        searchedAt
      });
    }
  });

  return records;
}

function nestedText(record: RawNiaSearchResult, key: string, nestedKeys: string[]) {
  const value = record[key];
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  return firstText(value as RawNiaSearchResult, nestedKeys);
}

function providerFromText(value: string) {
  const normalized = value.toLowerCase();
  const providers = [
    ["Lambda Cloud", /\blambda(?:\s+cloud|\s+labs)?\b/],
    ["Prime Intellect", /\bprime\s+intellect\b/],
    ["Intel Developer Cloud", /\bintel\s+developer\s+cloud\b|\bgaudi\b/],
    ["Google Cloud TPU", /\bgcp(?:\s+tpu)?\b|\bgoogle\s+cloud\s+tpu\b|\btpu\b/],
    ["Vast.ai", /\bvast(?:\.ai)?\b/],
    ["CoreWeave", /\bcoreweave\b/],
    ["Tensorlake", /\btensorlake\b/],
    ["TensorWave", /\btensorwave\b/],
    ["MacStadium", /\bmacstadium\b/],
    ["SkyPilot", /\bskypilot\b/],
    ["RunPod", /\brunpod\b|\brun\s+pod\b/],
    ["Modal", /\bmodal\b/],
    ["Vultr", /\bvultr\b/]
  ] as const;
  return providers.find(([, pattern]) => pattern.test(normalized))?.[0];
}

function providerName(value?: string) {
  if (!value) {
    return undefined;
  }
  return providerFromText(value) ?? clean(value, 64);
}

function acceleratorFromText(value: string) {
  const match = value.match(/\b(?:NVIDIA\s+)?(?:H100|H200|B200|A100|A40|A16|A10G?|L40S?|L4|T4|V100|RTX\s?4090|MI300X|MI325X|MI355X|TPU\s?v\d+[a-z]?|Gaudi\s?\d?)\b/i);
  return match ? clean(match[0].replace(/\s+/g, " "), 48) : undefined;
}

function regionFromText(value: string) {
  const cloudRegion = value.match(/\b(?:us|eu|ap|sa|ca|me|af)-[a-z]+-\d[a-z]?\b/i);
  if (cloudRegion) {
    return cloudRegion[0];
  }
  const code = Array.from(value.matchAll(/\b[a-z]{3}\b|\b[A-Z]{2,3}\b/g))
    .map((match) => match[0])
    .find((match) => !["GPU", "SKU", "USD"].includes(match.toUpperCase()));
  return code;
}

function availabilityFromText(value: string) {
  const normalized = value.toLowerCase();
  if (/\bunavailable\b|\bout of capacity\b|\bsold out\b/.test(normalized)) {
    return "unavailable";
  }
  if (/\bavailable\b|\bin stock\b|\bcapacity\b/.test(normalized)) {
    return "available";
  }
  if (/\blive\b|\bconnected\b/.test(normalized)) {
    return "live";
  }
  return undefined;
}

function normalizeAvailability(value: string | undefined) {
  if (!value) {
    return undefined;
  }
  if (value === "true") {
    return "available";
  }
  if (value === "false") {
    return "unavailable";
  }
  return clean(value, 48);
}

function cleanOptional(value: string | undefined, maxLength: number) {
  return value ? clean(value, maxLength) : undefined;
}

function clean(value: string, maxLength: number) {
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLength) {
    return cleaned;
  }
  return `${cleaned.slice(0, maxLength - 3).trimEnd()}...`;
}

function formatHourlyPrice(value: number) {
  if (value < 0.1) {
    return `$${value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "")}/hr`;
  }
  return `$${value.toFixed(2)}/hr`;
}

function sourceHost(source: string) {
  return source.replace(/^nia:\/\//, "").replace(/^https?:\/\//, "").split(/[/?#]/)[0] || "indexed source";
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
