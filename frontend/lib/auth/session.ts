import crypto from "node:crypto";

import { cookies } from "next/headers";

import { getSessionSecret } from "@/lib/config";
import { type Role, roleForUser } from "@/lib/auth/roles";
import type { VerifiedUser } from "@/lib/auth/google";

export const SESSION_COOKIE = "ops_session";
const MAX_AGE_SECONDS = 60 * 60 * 8; // 8 hours

export interface Session {
  sub: string; // immutable user key
  email: string | null;
  name: string | null;
  role: Role;
  exp: number; // unix seconds
}

function sign(payload: string): string {
  return crypto.createHmac("sha256", getSessionSecret()).update(payload).digest("base64url");
}

export function encodeSession(session: Session): string {
  const payload = Buffer.from(JSON.stringify(session)).toString("base64url");
  return `${payload}.${sign(payload)}`;
}

export function decodeSession(token: string): Session | null {
  const [payload, signature] = token.split(".");
  if (!payload || !signature) return null;
  const expected = sign(payload);
  // Constant-time compare; bail if lengths differ (timingSafeEqual requires equal length).
  if (signature.length !== expected.length) return null;
  if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) return null;
  try {
    const session = JSON.parse(Buffer.from(payload, "base64url").toString()) as Session;
    if (typeof session.exp !== "number" || session.exp < Date.now() / 1000) return null;
    return session;
  } catch {
    return null;
  }
}

export async function createSession(user: VerifiedUser): Promise<Session> {
  const session: Session = {
    sub: user.sub,
    email: user.email,
    name: user.name,
    role: roleForUser(user),
    exp: Math.floor(Date.now() / 1000) + MAX_AGE_SECONDS,
  };
  const store = await cookies();
  store.set(SESSION_COOKIE, encodeSession(session), {
    httpOnly: true, // never readable by client-side JS
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
  return session;
}

export async function getSession(): Promise<Session | null> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  return token ? decodeSession(token) : null;
}

export async function destroySession(): Promise<void> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
}
