import { NextResponse } from "next/server";

import { verifyGoogleIdToken } from "@/lib/auth/google";
import { createSession, destroySession } from "@/lib/auth/session";

// Token verification + session creation must run on Node (google-auth-library + node:crypto).
export const runtime = "nodejs";

export async function POST(request: Request) {
  let credential: unknown;
  try {
    ({ credential } = await request.json());
  } catch {
    return NextResponse.json({ error: "invalid body" }, { status: 400 });
  }
  if (typeof credential !== "string") {
    return NextResponse.json({ error: "missing credential" }, { status: 400 });
  }
  try {
    const user = await verifyGoogleIdToken(credential);
    const session = await createSession(user);
    return NextResponse.json({ ok: true, role: session.role });
  } catch {
    return NextResponse.json({ error: "invalid token" }, { status: 401 });
  }
}

export async function DELETE() {
  await destroySession();
  return NextResponse.json({ ok: true });
}
