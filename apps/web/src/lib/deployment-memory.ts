import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { randomBytes } from "node:crypto";
import { tmpdir } from "node:os";

import type { DeploymentObjective, NiaContextSnippet } from "@crucible/shared/crucible-contract";

import { getUserForSessionToken, sessionCookieName } from "./server-auth";

export type DeploymentMemoryOutcome = "planned" | "ready" | "failed" | "stopped";

export interface DeploymentMemoryEntry {
  id: string;
  userId: string;
  sessionId: string;
  prompt: string;
  modelId: string;
  objective: DeploymentObjective;
  provider: string;
  accelerator: string;
  estimatedHourlyUsd: number;
  outcome: DeploymentMemoryOutcome;
  lesson: string;
  createdAt: string;
}

export interface DeploymentMemoryInput {
  userId: string;
  sessionId: string;
  prompt: string;
  modelId: string;
  objective: DeploymentObjective;
  provider: string;
  accelerator: string;
  estimatedHourlyUsd: number;
  outcome: DeploymentMemoryOutcome;
  lesson?: string;
}

interface MemoryStore {
  entries: DeploymentMemoryEntry[];
}

function storePath() {
  return process.env.CRUCIBLE_MEMORY_STORE_PATH ?? join(tmpdir(), "crucible-web-memory.json");
}

function loadStore(): MemoryStore {
  const path = storePath();
  if (!existsSync(path)) {
    return { entries: [] };
  }
  return JSON.parse(readFileSync(path, "utf8")) as MemoryStore;
}

function saveStore(store: MemoryStore) {
  const path = storePath();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(store, null, 2));
}

export function recordDeploymentMemory(input: DeploymentMemoryInput) {
  const entry: DeploymentMemoryEntry = {
    ...input,
    id: `memory_${randomBytes(10).toString("base64url")}`,
    lesson: clean(input.lesson || defaultLesson(input), 260),
    createdAt: new Date().toISOString()
  };
  const store = loadStore();
  store.entries.push(entry);
  saveStore({
    entries: store.entries
      .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
      .slice(-200)
  });
  return entry;
}

export function listDeploymentMemory(userId: string, sessionId: string, limit = 8) {
  return loadStore().entries
    .filter((entry) => entry.userId === userId && entry.sessionId === sessionId)
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
    .slice(0, limit);
}

export function deploymentMemoryInsights(entries: DeploymentMemoryEntry[]) {
  return entries
    .map((entry) => entry.lesson)
    .filter(Boolean)
    .slice(0, 4);
}

export function deploymentMemorySnippets(entries: DeploymentMemoryEntry[]): NiaContextSnippet[] {
  return entries.slice(0, 4).map((entry) => ({
    id: entry.id,
    source: `memory://session/${entry.id}`,
    title: "Past session memory",
    excerpt: `${entry.modelId}: ${entry.lesson}`,
    usedFor: "Avoid repeating failed deployment choices and reuse successful deployment patterns.",
    searchedAt: entry.createdAt
  }));
}

export function deploymentMemoryIdentity(request: Request) {
  const sessionId = readCookie(request.headers.get("cookie") ?? "", sessionCookieName) ?? "anonymous-session";
  const user = getUserForSessionToken(sessionId);
  return {
    userId: user?.id ?? "anonymous-user",
    sessionId
  };
}

function readCookie(header: string, name: string) {
  return header
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function defaultLesson(input: DeploymentMemoryInput) {
  if (input.outcome === "failed") {
    return `${input.provider} ${input.accelerator} failed for ${input.modelId}; avoid repeating this placement without a new health signal.`;
  }
  if (input.outcome === "ready") {
    return `${input.provider} ${input.accelerator} reached ready for ${input.modelId}; prefer this placement when the objective matches.`;
  }
  return `${input.provider} ${input.accelerator} was planned for ${input.modelId} at ${input.estimatedHourlyUsd}/hr.`;
}

function clean(value: string, maxLength: number) {
  const cleaned = value.replace(/\s+/g, " ").trim();
  if (cleaned.length <= maxLength) {
    return cleaned;
  }
  return `${cleaned.slice(0, maxLength - 3).trimEnd()}...`;
}
