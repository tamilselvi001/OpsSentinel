"use client";

export default function SignOutButton() {
  async function signOut() {
    await fetch("/api/auth", { method: "DELETE" });
    window.location.href = "/login";
  }
  return (
    <button
      type="button"
      onClick={signOut}
      className="rounded-md px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
    >
      Sign out
    </button>
  );
}
