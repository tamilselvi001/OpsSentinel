// Runtime configuration. On Cloud Run these env vars are injected from Secret Manager
// (google-oauth-client-id, database-url); nothing secret is committed.

export type DataMode = "mock" | "live";

export function getDataMode(): DataMode {
  return process.env.OPSSENTINEL_DATA_MODE === "live" ? "live" : "mock";
}

/** Server-side OAuth client id used as the token audience during verification. */
export function getOAuthClientId(): string {
  const value = process.env.GOOGLE_OAUTH_CLIENT_ID;
  if (!value) throw new Error("GOOGLE_OAUTH_CLIENT_ID is not set");
  return value;
}

/** Client-visible OAuth client id for the Google Identity button (client ids are not secret). */
export function getPublicOAuthClientId(): string {
  return (
    process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID ?? process.env.GOOGLE_OAUTH_CLIENT_ID ?? ""
  );
}

/** Secret used to HMAC-sign the session cookie. Injected from Secret Manager in cloud. */
export function getSessionSecret(): string {
  return process.env.SESSION_SECRET ?? "dev-insecure-session-secret-change-me";
}

/** Emails granted the director role (reliability dashboard); everyone else is an SRE. */
export function getDirectorEmails(): string[] {
  return (process.env.OPSSENTINEL_DIRECTOR_EMAILS ?? "")
    .split(",")
    .map((entry) => entry.trim().toLowerCase())
    .filter(Boolean);
}

/** Node-pg connection string (strips the SQLAlchemy `+psycopg` driver suffix if present). */
export function getDatabaseUrl(): string {
  return (process.env.DATABASE_URL ?? "").replace("postgresql+psycopg://", "postgresql://");
}

/** Base URL of the Arize Phoenix UI for per-incident trace deep-links. */
export function getPhoenixBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PHOENIX_URL ??
    process.env.PHOENIX_COLLECTOR_ENDPOINT ??
    "http://localhost:6006"
  );
}
