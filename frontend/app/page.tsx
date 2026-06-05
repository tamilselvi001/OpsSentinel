import { redirect } from "next/navigation";

import { landingPathForRole } from "@/lib/auth/roles";
import { getSession } from "@/lib/auth/session";

// Entry point: route to the role's landing view, or to login when unauthenticated.
export default async function Home() {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }
  redirect(landingPathForRole(session.role));
}
