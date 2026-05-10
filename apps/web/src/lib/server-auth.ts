import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { pbkdf2Sync, randomBytes, timingSafeEqual } from "node:crypto";
import { tmpdir } from "node:os";
import { createClient } from "@insforge/sdk";

export const sessionCookieName = "crucible_session";
export const oauthVerifierCookieName = "crucible_oauth_verifier";
export const insforgeRefreshCookieName = "crucible_insforge_refresh";

export type OAuthProvider = "google" | "github";

export interface AuthConfig {
  requireEmailVerification: boolean;
  passwordMinLength: number;
  verifyEmailMethod: "code" | "link";
  resetPasswordMethod: "code" | "link";
  oAuthProviders: OAuthProvider[];
}

export interface PublicUser {
  id: string;
  email: string;
  role: "admin" | "user";
}

interface AuthSession {
  token: string;
  refreshToken?: string;
  csrfToken?: string;
  createdAt: string;
}

interface StoredUser {
  id: string;
  email: string;
  passwordHash: string;
  role: "admin" | "user";
  createdAt: string;
}

interface StoredSession {
  token: string;
  userId: string;
  createdAt: string;
}

interface AuthStore {
  users: StoredUser[];
  sessions: StoredSession[];
}

const iterations = 210_000;

function storePath() {
  return process.env.CRUCIBLE_AUTH_STORE_PATH ?? join(tmpdir(), "crucible-web-auth.json");
}

function insforgeBaseUrl() {
  return process.env.INSFORGE_API_BASE_URL?.replace(/\/$/, "");
}

function insforgeSdkBaseUrl() {
  return (process.env.NEXT_PUBLIC_INSFORGE_URL || process.env.INSFORGE_API_BASE_URL)?.replace(/\/$/, "");
}

function insforgeAnonKey() {
  return process.env.INSFORGE_ANON_KEY || process.env.NEXT_PUBLIC_INSFORGE_ANON_KEY;
}

function defaultAuthConfig(): AuthConfig {
  return {
    requireEmailVerification: false,
    passwordMinLength: 8,
    verifyEmailMethod: "code",
    resetPasswordMethod: "code",
    oAuthProviders: []
  };
}

function normalizeOAuthProviders(value: unknown): OAuthProvider[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((provider): provider is OAuthProvider => provider === "google" || provider === "github");
}

function normalizeMethod(value: unknown): "code" | "link" {
  return value === "link" ? "link" : "code";
}

function loadStore(): AuthStore {
  const path = storePath();
  if (!existsSync(path)) {
    return { users: [], sessions: [] };
  }
  return JSON.parse(readFileSync(path, "utf8")) as AuthStore;
}

function saveStore(store: AuthStore) {
  const path = storePath();
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(store, null, 2));
}

function publicUser(user: StoredUser): PublicUser {
  return {
    id: user.id,
    email: user.email,
    role: user.role
  };
}

function normalizeEmail(email: unknown) {
  return typeof email === "string" ? email.trim().toLowerCase() : "";
}

function validatePassword(password: unknown) {
  if (typeof password !== "string" || password.length < 8) {
    throw new Error("Password must be at least 8 characters.");
  }
  return password;
}

function hashPassword(password: string) {
  const salt = randomBytes(16);
  const digest = pbkdf2Sync(password, salt, iterations, 32, "sha256");
  return `pbkdf2_sha256$${iterations}$${salt.toString("hex")}$${digest.toString("hex")}`;
}

function verifyPassword(password: string, stored: string) {
  const [algorithm, storedIterations, saltHex, digestHex] = stored.split("$");
  if (algorithm !== "pbkdf2_sha256" || !storedIterations || !saltHex || !digestHex) {
    return false;
  }
  const expected = Buffer.from(digestHex, "hex");
  const actual = pbkdf2Sync(password, Buffer.from(saltHex, "hex"), Number(storedIterations), expected.length, "sha256");
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

export async function signup(emailInput: unknown, passwordInput: unknown) {
  if (insforgeBaseUrl()) {
    return signupWithInsForge(emailInput, passwordInput);
  }
  return signupLocal(emailInput, passwordInput);
}

export async function login(emailInput: unknown, passwordInput: unknown) {
  if (insforgeBaseUrl()) {
    return loginWithInsForge(emailInput, passwordInput);
  }
  return loginLocal(emailInput, passwordInput);
}

export async function getAuthConfig(): Promise<AuthConfig> {
  const baseUrl = insforgeBaseUrl();
  if (!baseUrl) {
    return defaultAuthConfig();
  }
  try {
    const response = await fetch(`${baseUrl}/api/auth/public-config`, { cache: "no-store" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || !payload || typeof payload !== "object" || Array.isArray(payload)) {
      return defaultAuthConfig();
    }
    const record = payload as Record<string, unknown>;
    return {
      requireEmailVerification: record.requireEmailVerification === true,
      passwordMinLength: typeof record.passwordMinLength === "number" ? record.passwordMinLength : 8,
      verifyEmailMethod: normalizeMethod(record.verifyEmailMethod),
      resetPasswordMethod: normalizeMethod(record.resetPasswordMethod),
      oAuthProviders: normalizeOAuthProviders(record.oAuthProviders)
    };
  } catch {
    return defaultAuthConfig();
  }
}

function signupLocal(emailInput: unknown, passwordInput: unknown) {
  const email = normalizeEmail(emailInput);
  if (!email || !email.includes("@")) {
    throw new Error("A valid email is required.");
  }
  const password = validatePassword(passwordInput);
  const store = loadStore();
  if (store.users.some((user) => user.email === email)) {
    throw new Error("User already exists.");
  }
  const user: StoredUser = {
    id: `user_${randomBytes(12).toString("base64url")}`,
    email,
    passwordHash: hashPassword(password),
    role: store.users.length === 0 ? "admin" : "user",
    createdAt: new Date().toISOString()
  };
  const session = {
    token: `sess_${randomBytes(18).toString("base64url")}`,
    userId: user.id,
    createdAt: new Date().toISOString()
  };
  store.users.push(user);
  store.sessions.push(session);
  saveStore(store);
  return { user: publicUser(user), session };
}

function loginLocal(emailInput: unknown, passwordInput: unknown) {
  const email = normalizeEmail(emailInput);
  const password = typeof passwordInput === "string" ? passwordInput : "";
  const store = loadStore();
  const user = store.users.find((item) => item.email === email);
  if (!user || !verifyPassword(password, user.passwordHash)) {
    throw new Error("Invalid email or password.");
  }
  const session = {
    token: `sess_${randomBytes(18).toString("base64url")}`,
    userId: user.id,
    createdAt: new Date().toISOString()
  };
  store.sessions.push(session);
  saveStore(store);
  return { user: publicUser(user), session };
}

export function getUserForSessionToken(token: string): PublicUser | null {
  if (!token) {
    return null;
  }
  const store = loadStore();
  const session = store.sessions.find((item) => item.token === token);
  if (!session) {
    return null;
  }
  const user = store.users.find((item) => item.id === session.userId);
  return user ? publicUser(user) : null;
}

async function signupWithInsForge(emailInput: unknown, passwordInput: unknown) {
  const email = normalizeEmail(emailInput);
  if (!email || !email.includes("@")) {
    throw new Error("A valid email is required.");
  }
  const password = validatePassword(passwordInput);
  return callInsForgeAuth("/api/auth/users?client_type=server", { email, password });
}

async function loginWithInsForge(emailInput: unknown, passwordInput: unknown) {
  const email = normalizeEmail(emailInput);
  const password = typeof passwordInput === "string" ? passwordInput : "";
  return callInsForgeAuth("/api/auth/sessions?client_type=server", { email, password });
}

async function callInsForgeAuth(path: string, body: { email: string; password: string }) {
  const baseUrl = insforgeBaseUrl();
  if (!baseUrl) {
    throw new Error("InsForge is not configured.");
  }
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store"
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(insforgeError(payload, response.status));
  }
  const token = typeof payload.accessToken === "string" ? payload.accessToken : "";
  if (!token) {
    throw new Error("InsForge did not return an access token. Email verification may be required.");
  }
  return {
    user: normalizeInsForgeUser(payload.user, body.email),
    session: {
      token,
      refreshToken: typeof payload.refreshToken === "string" ? payload.refreshToken : undefined,
      csrfToken: typeof payload.csrfToken === "string" ? payload.csrfToken : undefined,
      createdAt: new Date().toISOString()
    } satisfies AuthSession
  };
}

export function safeAuthRedirect(value: string | null, fallback = "/dashboard") {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  return value;
}

function createInsForgeServerClient() {
  const baseUrl = insforgeSdkBaseUrl();
  const anonKey = insforgeAnonKey();
  if (!baseUrl || !anonKey) {
    throw new Error("InsForge OAuth requires NEXT_PUBLIC_INSFORGE_URL and INSFORGE_ANON_KEY.");
  }
  return createClient({
    baseUrl,
    anonKey,
    isServerMode: true
  });
}

export async function startInsForgeOAuth(provider: OAuthProvider, appOrigin: string, nextPath: string) {
  const config = await getAuthConfig();
  if (!config.oAuthProviders.includes(provider)) {
    throw new Error(`${provider} OAuth is not enabled for this InsForge project.`);
  }
  const redirectTo = new URL("/api/auth/callback", appOrigin);
  redirectTo.searchParams.set("next", safeAuthRedirect(nextPath));
  const { data, error } = await createInsForgeServerClient().auth.signInWithOAuth({
    provider,
    redirectTo: redirectTo.toString(),
    skipBrowserRedirect: true
  });
  if (error || !data?.url || !data?.codeVerifier) {
    throw new Error(error?.message ?? "OAuth init failed.");
  }
  return {
    url: data.url,
    codeVerifier: data.codeVerifier
  };
}

export async function finishInsForgeOAuth(code: string, codeVerifier: string) {
  const { data, error } = await createInsForgeServerClient().auth.exchangeOAuthCode(code, codeVerifier);
  if (error || !data?.accessToken) {
    throw new Error(error?.message ?? "OAuth exchange failed.");
  }
  return {
    user: normalizeInsForgeUser(data.user, ""),
    session: {
      token: data.accessToken,
      refreshToken: typeof data.refreshToken === "string" ? data.refreshToken : undefined,
      createdAt: new Date().toISOString()
    } satisfies AuthSession
  };
}

function normalizeInsForgeUser(value: unknown, fallbackEmail: string): PublicUser {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {
      id: fallbackEmail,
      email: fallbackEmail,
      role: "user"
    };
  }
  const record = value as Record<string, unknown>;
  const role = record.role === "project_admin" ? "admin" : "user";
  return {
    id: typeof record.id === "string" ? record.id : fallbackEmail,
    email: typeof record.email === "string" ? normalizeEmail(record.email) : fallbackEmail,
    role
  };
}

function insforgeError(payload: unknown, status: number) {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const record = payload as Record<string, unknown>;
    for (const key of ["message", "error"]) {
      if (typeof record[key] === "string" && record[key]) {
        return record[key];
      }
    }
  }
  return `InsForge auth failed with HTTP ${status}.`;
}
