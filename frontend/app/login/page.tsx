import GoogleSignIn from "@/components/GoogleSignIn";
import { getPublicOAuthClientId } from "@/lib/config";

// Server component: reads the (non-secret) OAuth client id at runtime and hands it to the client
// widget — so Cloud Run can inject it from Secret Manager without a build-time NEXT_PUBLIC value.
export default function LoginPage() {
  const clientId = getPublicOAuthClientId();
  return (
    <main className="flex flex-1 items-center justify-center bg-zinc-50 dark:bg-black">
      <div className="flex w-full max-w-sm flex-col items-center gap-6 rounded-xl border border-zinc-200 bg-white p-10 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          OpsSentinel
        </h1>
        <p className="text-center text-sm text-zinc-600 dark:text-zinc-400">
          Sign in with Google to access the incident console.
        </p>
        <GoogleSignIn clientId={clientId} />
      </div>
    </main>
  );
}
