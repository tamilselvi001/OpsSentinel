import type { ReactNode } from "react";

import { redirect } from "next/navigation";

import Nav from "@/components/Nav";
import { getSession } from "@/lib/auth/session";

// Server-side guard: unauthenticated requests can never reach a dashboard route.
export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const session = await getSession();
  if (!session) {
    redirect("/login");
  }
  return (
    <div className="flex flex-1 flex-col">
      <Nav session={session} />
      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
    </div>
  );
}
