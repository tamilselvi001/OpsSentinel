import { getDirectorEmails } from "@/lib/config";

export type Role = "director" | "sre";

/** Role separation driven by the verified token (the `sub`/email), not client state. */
export function roleForUser(user: { email: string | null }): Role {
  if (user.email && getDirectorEmails().includes(user.email.toLowerCase())) {
    return "director";
  }
  return "sre";
}

/** Where each role lands by default. */
export function landingPathForRole(role: Role): string {
  return role === "director" ? "/reliability" : "/incidents";
}
