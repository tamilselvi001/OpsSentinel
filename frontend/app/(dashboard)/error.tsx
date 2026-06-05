"use client";

// Route-segment error boundary: a data hiccup degrades gracefully instead of throwing on the client.
export default function DashboardError({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-8 text-center dark:border-red-900 dark:bg-red-950">
      <h2 className="text-lg font-semibold text-red-800 dark:text-red-300">
        Could not load this view
      </h2>
      <p className="mt-1 text-sm text-red-600 dark:text-red-400">
        The incident data is temporarily unavailable.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-4 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
      >
        Try again
      </button>
    </div>
  );
}
