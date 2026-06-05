import { OAuth2Client } from "google-auth-library";

import { getOAuthClientId } from "@/lib/config";

export interface VerifiedUser {
  sub: string; // immutable primary key for user mapping
  email: string | null;
  name: string | null;
  picture: string | null;
}

const client = new OAuth2Client();

/**
 * Cryptographically verify a Google ID token with the official client library (prevents spoofing).
 * The audience is checked against google-oauth-client-id from Secret Manager.
 */
export async function verifyGoogleIdToken(idToken: string): Promise<VerifiedUser> {
  const ticket = await client.verifyIdToken({ idToken, audience: getOAuthClientId() });
  const payload = ticket.getPayload();
  if (!payload?.sub) {
    throw new Error("token has no subject");
  }
  return {
    sub: payload.sub,
    email: payload.email ?? null,
    name: payload.name ?? null,
    picture: payload.picture ?? null,
  };
}
