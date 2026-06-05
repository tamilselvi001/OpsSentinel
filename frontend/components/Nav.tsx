import Link from "next/link";

import SignOutButton from "@/components/SignOutButton";
import type { Session } from "@/lib/auth/session";

const LINKS = [
  { href: "/incidents", label: "Incidents" },
  { href: "/reliability", label: "Reliability" },
  { href: "/health", label: "Health" },
];

export default function Nav({ session }: { session: Session }) {
  return (
    <header className="flex items-center justify-between border-b border-zinc-200 px-6 py-3 dark:border-zinc-800">
      <div className="flex items-center gap-6">
        <Link href="/" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          OpsSentinel
        </Link>
        <nav className="flex gap-1">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="rounded-md px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
      <div className="flex items-center gap-3 text-sm text-zinc-500">
        <span>
          {session.email ?? session.sub}{" "}
          <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
            {session.role}
          </span>
        </span>
        <SignOutButton />
      </div>
    </header>
  );
}
