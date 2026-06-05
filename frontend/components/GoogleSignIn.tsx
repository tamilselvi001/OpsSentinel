"use client";

import Script from "next/script";
import { useRef, useState } from "react";

interface GsiId {
  initialize(config: {
    client_id: string;
    callback: (response: { credential?: string }) => void;
  }): void;
  renderButton(parent: HTMLElement, options: Record<string, unknown>): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GsiId } };
  }
}

export default function GoogleSignIn({ clientId }: { clientId: string }) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleCredential(response: { credential?: string }) {
    if (!response.credential) {
      setError("No credential returned by Google.");
      return;
    }
    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
    });
    if (res.ok) {
      window.location.href = "/";
    } else {
      setError("Sign-in failed. Your account may not be authorized.");
    }
  }

  function initGsi() {
    if (!window.google || !buttonRef.current || !clientId) return;
    window.google.accounts.id.initialize({ client_id: clientId, callback: handleCredential });
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: "filled_blue",
      size: "large",
      text: "signin_with",
    });
  }

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={initGsi}
      />
      <div ref={buttonRef} />
      {!clientId && (
        <p className="text-center text-xs text-amber-600">OAuth client id is not configured.</p>
      )}
      {error && <p className="text-center text-sm text-red-600">{error}</p>}
    </>
  );
}
