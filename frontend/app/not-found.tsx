import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-3 p-12 text-center">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Not found</h1>
      <p className="text-sm text-zinc-500">This incident or page does not exist.</p>
      <Link href="/incidents" className="text-sm text-blue-600 hover:underline">
        Go to incidents
      </Link>
    </main>
  );
}
